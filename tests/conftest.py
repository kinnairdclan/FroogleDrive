import os

import pytest
from werkzeug.security import generate_password_hash

from app import create_app

USERNAME = "admin"
PASSWORD = "s3cret"


@pytest.fixture
def data_root(tmp_path):
    root = tmp_path / "data"
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "a.txt").write_text("alpha")
    (root / "sub" / "b.txt").write_text("bravo")
    (root / "sub" / "deep" / "c.txt").write_text("charlie")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")
    os.symlink(outside, root / "escape")
    os.symlink(outside / "secret.txt", root / "sub" / "escape.txt")
    os.symlink(root / "a.txt", root / "inner-link.txt")
    return root


@pytest.fixture
def app(tmp_path, data_root):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "FROOGLEDRIVE_ROOT": str(data_root),
        "FROOGLEDRIVE_USERNAME": USERNAME,
        "FROOGLEDRIVE_PASSWORD_HASH": generate_password_hash(PASSWORD),
        "DATABASE": str(tmp_path / "shares.db"),
        "WTF_CSRF_ENABLED": False,
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    resp = client.post("/login", data={"username": USERNAME, "password": PASSWORD})
    assert resp.status_code == 302
    return client


@pytest.fixture
def make_share(auth_client):
    def make(path, expiry="never", description=""):
        resp = auth_client.post("/shares", data={"path": path, "expiry": expiry,
                                                 "description": description})
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        start = html.index("/shares/", html.index('id="share-link"') - 200) + len("/shares/")
        return html[start:start + 32]
    return make
