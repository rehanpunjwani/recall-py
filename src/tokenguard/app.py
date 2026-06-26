from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from tokenguard.engine import answer as engine_answer
from tokenguard.metrics import (
    record_proxy_cache_hit,
    record_proxy_compress,
    record_proxy_local_first,
)
from tokenguard.ollama_client import OllamaClient
from tokenguard.proxy import (
    canonical_request_hash,
    compress_messages,
    forward_streaming,
    openai_style_response,
)
from tokenguard.settings import AppSettings
from tokenguard.store.db import connect, migrate
from tokenguard.store.repository import proxy_cache_get, proxy_cache_put


def create_app(settings: AppSettings, conn: sqlite3.Connection) -> FastAPI:
    app = FastAPI(title="TokenGuard", version="0.1.0")
    ollama = OllamaClient(settings.ollama)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        ok = await ollama.health()
        return {"status": "ok" if ok else "degraded", "ollama_reachable": ok}

    if settings.proxy.enabled and settings.proxy.upstream_base_url.strip():

        @app.post("/v1/chat/completions")
        async def chat_completions(request: Request) -> Response:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"error": {"message": "Invalid JSON"}}, status_code=400)

            if body.get("stream") is True:
                return await forward_streaming(body, settings.proxy)

            h = canonical_request_hash(body)
            cached = proxy_cache_get(conn, h, ttl_seconds=settings.proxy.cache_ttl_seconds)
            if cached:
                record_proxy_cache_hit(conn, cached_json=cached)
                return Response(content=cached, media_type="application/json")

            if settings.proxy.try_local_first:
                messages = body.get("messages") or []
                last_user = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        c = m.get("content")
                        if isinstance(c, str):
                            last_user = c
                        break
                if last_user.strip():
                    tid = request.headers.get("x-tokenguard-thread-id")
                    draft = await engine_answer(
                        conn,
                        settings,
                        ollama,
                        query=last_user,
                        thread_id=tid,
                    )
                    if draft.get("mode") == "draft" and draft.get("draft"):
                        record_proxy_local_first(
                            conn,
                            query=last_user,
                            context=str(draft.get("citations", "")),
                            draft=str(draft["draft"]),
                        )
                        resp = openai_style_response(
                            body.get("model", "tokenguard-local"),
                            draft["draft"],
                        )
                        payload = json.dumps(resp)
                        proxy_cache_put(conn, h, payload, max_entries=settings.proxy.cache_max_entries)
                        return Response(content=payload, media_type="application/json")

            upstream = settings.proxy.upstream_base_url.rstrip("/")
            api_key_env = settings.proxy.upstream_api_key_env
            api_key = os.environ.get(api_key_env, "")

            forward_body = dict(body)
            original_messages = forward_body.get("messages") or []
            compressed = compress_messages(original_messages)
            chars_removed = sum(
                max(0, len(str(m.get("content", ""))) - len(str(c.get("content", ""))))
                for m, c in zip(original_messages, compressed, strict=False)
            )
            record_proxy_compress(conn, chars_removed=chars_removed)
            forward_body["messages"] = compressed

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            url = f"{upstream}/v1/chat/completions"
            timeout = httpx.Timeout(120.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, json=forward_body, headers=headers)
            text = r.text
            if r.status_code == 200:
                proxy_cache_put(conn, h, text, max_entries=settings.proxy.cache_max_entries)
            return Response(content=text, media_type="application/json", status_code=r.status_code)

    return app


def open_connection(settings: AppSettings) -> sqlite3.Connection:
    path = settings.resolved_db_path()
    c = connect(path)
    migrate(c)
    return c
