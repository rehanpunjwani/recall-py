from tokenguard.threads import resolve_workspace_thread, thread_id_for_fingerprint


def test_resolve_workspace_thread_ignores_chat_id():
    ws = "/tmp/my-project"
    tid, fp = resolve_workspace_thread("old-chat-uuid", ws)
    assert fp == ws
    assert tid == thread_id_for_fingerprint(ws)


def test_resolve_workspace_thread_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKENGUARD_WORKSPACE", str(tmp_path))
    tid, fp = resolve_workspace_thread(None, "")
    assert fp == str(tmp_path)
    assert tid == thread_id_for_fingerprint(str(tmp_path))
