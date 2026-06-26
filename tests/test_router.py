from tokenguard.router import should_force_escalate


def test_escalate_keyword():
    hit, kw = should_force_escalate("This is about lawsuit stuff", ["lawsuit"])
    assert hit and kw == "lawsuit"


def test_no_escalate():
    hit, _ = should_force_escalate("hello world", ["lawsuit"])
    assert not hit
