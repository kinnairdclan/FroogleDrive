from datetime import datetime, timezone

import pytest
from werkzeug.security import generate_password_hash

from app import create_app, hash_password

ENV = {
    "SECRET_KEY": "env-secret",
    "FROOGLEDRIVE_USERNAME": "envuser",
    "FROOGLEDRIVE_PASSWORD_HASH": generate_password_hash("envpw"),
}


@pytest.fixture
def env_app(monkeypatch, tmp_path, data_root):
    """App configured purely from environment variables, as in Docker."""
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FROOGLEDRIVE_ROOT", str(data_root))
    monkeypatch.delenv("DATABASE", raising=False)

    def make(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return create_app(instance_path=str(tmp_path / "instance"))
    return make


def test_config_from_env(env_app, tmp_path, data_root):
    app = env_app(FROOGLEDRIVE_SECURE_COOKIES="yes", FROOGLEDRIVE_SUBTITLE="Sub")
    assert app.config["DATABASE"] == str(tmp_path / "instance" / "shares.db")
    assert (tmp_path / "instance" / "shares.db").exists()
    assert app.config["FROOGLEDRIVE_ROOT"] == str(data_root)
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["TRUST_PROXY"] == 0
    # CSRF is on outside the test config, so log in the way a browser does
    client = app.test_client()
    form = client.get("/login").get_data(as_text=True)
    token = form.split('name="csrf_token" value="')[1].split('"')[0]
    resp = client.post("/login", data={"username": "envuser", "password": "envpw", "csrf_token": token})
    assert resp.status_code == 302


@pytest.mark.parametrize("value", ["", "0", "no", "false"])
def test_secure_cookies_off(env_app, value):
    assert env_app(FROOGLEDRIVE_SECURE_COOKIES=value).config["SESSION_COOKIE_SECURE"] is False


def test_empty_trust_proxy_is_zero(env_app):
    assert env_app(FROOGLEDRIVE_TRUST_PROXY="").config["TRUST_PROXY"] == 0


def test_trust_proxy_uses_forwarded_host(env_app):
    app = env_app(FROOGLEDRIVE_TRUST_PROXY="1")
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    client.post("/login", data={"username": "envuser", "password": "envpw"})
    headers = {"X-Forwarded-Host": "files.example.com", "X-Forwarded-Proto": "https"}
    resp = client.post("/shares", data={"path": "a.txt"}, headers=headers)
    assert b"https://files.example.com/shares/" in resp.data


def test_filters(app):
    filesize = app.jinja_env.filters["filesize"]
    assert [filesize(n) for n in (0, 1023, 1024, 1536, 1024**2, 1024**3, 5 * 1024**4)] == [
        "0 B", "1023 B", "1.0 KB", "1.5 KB", "1.0 MB", "1.0 GB", "5.0 TB"]

    fmt = app.jinja_env.filters["datetime"]
    assert fmt(None) == ""
    assert fmt(datetime(2026, 1, 2, 3, 4)) == "2026-01-02 03:04"
    assert fmt(datetime(2026, 1, 2, 3, 4).timestamp()) == "2026-01-02 03:04"
    utc = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert fmt(utc.isoformat()) == utc.astimezone().strftime("%Y-%m-%d %H:%M")


def test_hash_password(monkeypatch, capsys):
    monkeypatch.setattr(hash_password.getpass, "getpass", lambda prompt: "hunter2")
    hash_password.main()
    from werkzeug.security import check_password_hash
    assert check_password_hash(capsys.readouterr().out.strip(), "hunter2")


@pytest.mark.parametrize("answers, message", [
    (["", ""], "must not be empty"),
    (["one", "two"], "do not match"),
])
def test_hash_password_rejects(monkeypatch, answers, message):
    replies = iter(answers)
    monkeypatch.setattr(hash_password.getpass, "getpass", lambda prompt: next(replies))
    with pytest.raises(SystemExit, match=message):
        hash_password.main()
