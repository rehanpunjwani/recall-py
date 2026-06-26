from tokenguard.text.redact import redact_text


def test_redact_api_key_pattern():
    patterns = [r"(?i)(api_key)\s*[:=]\s*[^\s]+"]
    s = 'api_key = "secret123" rest'
    out = redact_text(s, patterns)
    assert "secret123" not in out
    assert "[REDACTED]" in out
