import json

from nexus_nancy.auth import get_codex_token


def test_get_codex_token_returns_none_if_file_missing(tmp_path):
    assert get_codex_token(tmp_path / "missing.json") is None


def test_get_codex_token_returns_token_from_json(tmp_path):
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps({"access_token": "secret_token"}), encoding="utf-8")

    assert get_codex_token(session_file) == "secret_token"


def test_get_codex_token_handles_malformed_json(tmp_path):
    session_file = tmp_path / "bad.json"
    session_file.write_text("not json", encoding="utf-8")

    import pytest

    with pytest.raises(json.JSONDecodeError):
        get_codex_token(session_file)
