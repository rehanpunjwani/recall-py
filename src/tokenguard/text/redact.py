from __future__ import annotations

import re
from collections.abc import Iterable


def redact_text(text: str, patterns: Iterable[str]) -> str:
    out = text
    for pat in patterns:
        if not pat.strip():
            continue
        try:
            out = re.sub(pat, "[REDACTED]", out)
        except re.error:
            continue
    return out
