import pytest

from app import create_app


@pytest.mark.parametrize("url", ["/", "/browse/", "/browse/sub", "/shares", "/shares/new?path=a.txt"])
def test_login_required(client, url):
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_htmx_gets_hx_redirect(client):
    resp = client.get("/browse/sub", headers={"HX-Request": "true"})
    assert resp.status_code == 401
    assert "/login" in resp.headers["HX-Redirect"]


def test_bad_password(client):
    resp = client.post("/login?next=/browse/sub", data={"username": "admin", "password": "nope"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/login?next=/browse/sub"
    resp = client.get(resp.headers["Location"])
    assert resp.status_code == 401 and b"Invalid" in resp.data
    assert b"Invalid" not in client.get("/login").data  # shown once, not on refresh
    assert client.get("/browse/").status_code == 302


def test_login_redirects_to_next(client):
    resp = client.post("/login?next=/browse/sub", data={"username": "admin", "password": "s3cret"})
    assert resp.headers["Location"] == "/browse/sub"


@pytest.mark.parametrize("nxt", ["//evil.com", "/%5Cevil.com", "https://evil.com",
                                 "/%09/evil.com", "/%0a/evil.com", "/%0d/evil.com", "/%7f/evil.com"])
def test_open_redirect_blocked(client, nxt):
    resp = client.post(f"/login?next={nxt}", data={"username": "admin", "password": "s3cret"})
    assert resp.headers["Location"] == "/"


def test_throttle(client):
    for _ in range(5):
        client.post("/login", data={"username": "admin", "password": "x"},
                    environ_base={"REMOTE_ADDR": "10.9.9.9"})
    resp = client.post("/login", data={"username": "admin", "password": "s3cret"},
                       environ_base={"REMOTE_ADDR": "10.9.9.9"}, follow_redirects=True)
    assert resp.status_code == 401
    assert b"Too many" in resp.data


def test_missing_settings_fail_fast(tmp_path):
    with pytest.raises(RuntimeError, match="FROOGLEDRIVE_USERNAME"):
        create_app({"SECRET_KEY": "x" * 32, "FROOGLEDRIVE_USERNAME": None,
                    "FROOGLEDRIVE_PASSWORD_HASH": "x", "DATABASE": str(tmp_path / "db")})


@pytest.mark.parametrize("key", ["short", "change-me-to-a-long-random-string"])
def test_weak_secret_key_refused(tmp_path, key):
    with pytest.raises(RuntimeError, match="SECRET_KEY must be"):
        create_app({"SECRET_KEY": key, "FROOGLEDRIVE_USERNAME": "u",
                    "FROOGLEDRIVE_PASSWORD_HASH": "x", "DATABASE": str(tmp_path / "db")})


def test_csrf_enforced(app, auth_client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert auth_client.post("/shares", data={"path": "a.txt"}).status_code == 400
    assert auth_client.post("/logout").status_code == 400


def test_browse(auth_client):
    page = auth_client.get("/browse/").get_data(as_text=True)
    assert "a.txt" in page and "sub" in page and "escape" not in page
    assert "<html" in page
    assert "icons/folder.svg" in page and "icons/text-x-generic.svg" in page

    partial = auth_client.get("/browse/sub", headers={"HX-Request": "true"}).get_data(as_text=True)
    assert "b.txt" in partial and "<html" not in partial

    restore = auth_client.get("/browse/sub", headers={"HX-Request": "true",
                                                     "HX-History-Restore-Request": "true"})
    assert b"<html" in restore.data


@pytest.mark.parametrize("url", ["/browse/../outside", "/browse/%2e%2e/outside/secret.txt",
                                 "/browse/escape/secret.txt", "/browse/sub/escape.txt"])
def test_browse_traversal(auth_client, url):
    assert auth_client.get(url).status_code == 404


def test_browse_downloads_file(auth_client):
    resp = auth_client.get("/browse/sub/b.txt")
    assert resp.data == b"bravo"
    assert "attachment" in resp.headers["Content-Disposition"]


@pytest.mark.parametrize("asset", ["icons/folder.svg", "icons/application-x-generic.svg",
                                   "fonts/AdwaitaSans-Regular.woff2", "fonts/AdwaitaMono-Regular.woff2"])
def test_static_assets(client, asset):
    assert client.get(f"/static/{asset}").status_code == 200


@pytest.mark.parametrize("value", ["(Jason's Cloudshare System)", "Jason's Cloudshare System"])
def test_brand_subtitle(app, auth_client, value):
    app.config["FROOGLEDRIVE_SUBTITLE"] = value
    page = auth_client.get("/browse/").get_data(as_text=True)
    assert "(Jason&#39;s Cloudshare System)</span>" in page
    assert "((" not in page


def test_no_brand_subtitle(auth_client):
    assert b"brand-subtitle" not in auth_client.get("/browse/").data


def test_login_page(client):
    resp = client.get("/login")
    assert resp.status_code == 200 and b'name="password"' in resp.data


def test_index_redirects_to_browser(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/browse/"


def test_logout(auth_client):
    resp = auth_client.post("/logout")
    assert resp.status_code == 302 and resp.headers["Location"] == "/login"
    assert auth_client.get("/browse/").status_code == 302
