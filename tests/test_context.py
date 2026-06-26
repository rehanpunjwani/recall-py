from tokenguard.context import build_agent_context_message, format_context_injection


def test_format_context_empty():
    assert "tokenguard index" in format_context_injection([])


def test_build_agent_message_includes_citations():
    msg = build_agent_context_message(
        thread_id="tid-1",
        workspace_fingerprint="/tmp/proj",
        user_query="How do I run MCP?",
        citations=[
            {"chunk_id": "c1", "score": 0.85, "text": "Run tokenguard mcp-stdio via IDE."},
        ],
        top_score=0.85,
    )
    assert "RETRIEVED CONTEXT" in msg
    assert "c1" in msg
    assert "How do I run MCP?" in msg
    assert "thread_id='tid-1'" in msg
