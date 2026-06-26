from tokenguard.text.chunking import chunk_text


def test_chunk_text_overlap():
    text = "a" * 100
    parts = chunk_text(text, size=30, overlap=10)
    assert len(parts) >= 2
    assert all(len(p) <= 30 for p in parts)
