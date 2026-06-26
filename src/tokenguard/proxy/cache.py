from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any


def canonical_request_hash(body: dict[str, Any]) -> str:
    stable = {
        "model": body.get("model"),
        "messages": body.get("messages"),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
    }
    raw = json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compress_messages(messages: list[dict[str, Any]], max_chars: int = 4000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        m = dict(m)
        c = m.get("content")
        if isinstance(c, str) and len(c) > max_chars:
            m["content"] = c[:max_chars] + "\n...[truncated by TokenGuard]"
        out.append(m)
    return out


def openai_style_response(model: str, content: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
