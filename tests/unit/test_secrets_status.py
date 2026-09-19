"""Chapter 26: pure logic, no network, no process restart. Proves the
digest actually changes when the secret material changes, and that it
never contains the real secret value itself.
"""

from reorder_app.secrets_status import secret_digest


def test_the_digest_changes_when_the_underlying_secret_changes(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key-one")
    monkeypatch.setenv("DATABASE_URL", "postgresql://a")
    first = secret_digest()

    monkeypatch.setenv("GEMINI_API_KEY", "key-two")
    second = secret_digest()

    assert first != second


def test_the_digest_never_contains_the_real_secret_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-very-recognizable-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://b")

    digest = secret_digest()

    assert "a-very-recognizable-secret-value" not in digest
    assert len(digest) == 12
