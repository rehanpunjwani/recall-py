"""Stable workspace thread IDs shared by hooks, MCP, and CLI."""

from __future__ import annotations

import os
import uuid
from typing import Any


def workspace_fingerprint(payload: dict[str, Any]) -> str:
    for key in ("workspace_roots", "workspaceRoot", "workspace_root", "cwd", "rootPath"):
        val = payload.get(key)
        if isinstance(val, list) and val:
            return str(val[0])
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def thread_id_for_fingerprint(workspace_fp: str) -> str:
    fp = workspace_fp.strip() or "default"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tokenguard:{fp}"))


def thread_id_for_workspace(payload: dict[str, Any]) -> str:
    return thread_id_for_fingerprint(workspace_fingerprint(payload))


def default_workspace_fingerprint() -> str:
    env = os.environ.get("TOKENGUARD_WORKSPACE", "").strip()
    if env:
        return env
    return os.getcwd()


def resolve_workspace_thread(
    thread_id: str | None = None,
    workspace_fingerprint_arg: str = "",
) -> tuple[str, str]:
    fp = workspace_fingerprint_arg.strip() or default_workspace_fingerprint()
    return thread_id_for_fingerprint(fp), fp
