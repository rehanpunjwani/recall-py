from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi.responses import StreamingResponse

from tokenguard.settings import ProxyConfig


async def forward_streaming(body: dict[str, Any], cfg: ProxyConfig) -> StreamingResponse:
    upstream = cfg.upstream_base_url.rstrip("/")
    api_key_env = cfg.upstream_api_key_env
    api_key = os.environ.get(api_key_env, "")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{upstream}/v1/chat/completions"
    timeout = httpx.Timeout(120.0)

    async def gen():
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")
