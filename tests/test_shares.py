import io
import re
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_db

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")


def test_file_share_public(app, make_share):
    token = make_share("a.txt")
    assert TOKEN_RE.match(token)
    anon = app.test_client()  # fresh client, not logged in
    page = anon.get(f"/shares/{token}")
    assert page.status_code == 200 and b"a.txt" in page.data
    dl = anon.get(f"/shares/{token}?dl=1")
    assert dl.data == b"alpha"
    assert "attachment" in dl.headers["Content-Disposition"]
    assert anon.get(f"/shares/{token}/anything").status_code == 404
    assert anon.get(f"/shares/{token}.zip").status_code == 404


def test_range_request(app, make_share):
    token = make_share("a.txt")
    resp = app.test_client().get(f"/shares/{token}?dl=1", headers={"Range": "bytes=1-2"})
    assert resp.status_code == 206 and resp.data == b"lp"


def test_dir_share_public(app, make_share):
    token = make_share("sub")
    anon = app.test_client()
    page = anon.get(f"/shares/{token}").get_data(as_text=True)
    assert "b.txt" in page and "deep" in page and "escape" not in page
    assert b"charlie" == anon.get(f"/shares/{token}/deep/c.txt").data
    assert anon.get(f"/shares/{token}/deep").status_code == 200


@pytest.mark.parametrize("sub", ["..", "../a.txt", "%2e%2e/a.txt", "escape.txt", "deep/../../a.txt"])
def test_dir_share_cannot_escape(app, make_share, sub):
    token = make_share("sub")
    assert app.test_client().get(f"/shares/{token}/{sub}").status_code == 404


def test_zip(app, make_share):
    token = make_share("sub")
    resp = app.test_client().get(f"/shares/{token}.zip")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith('attachment; filename="sub.zip"')
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    assert sorted(zf.namelist()) == ["b.txt", "deep/c.txt"]
    assert zf.read("deep/c.txt") == b"charlie"
    assert int(resp.headers["Content-Length"]) == len(resp.data)


def test_share_root(app, make_share):
    token = make_share("")
    assert b"sub" in app.test_client().get(f"/shares/{token}").data


def test_unknown_token(client):
    assert client.get("/shares/" + "A" * 32).status_code == 404


def test_revoke(app, auth_client, make_share):
    token = make_share("a.txt")
    resp = auth_client.delete(f"/shares/{token}")
    assert resp.status_code == 200 and b"revoked" in resp.data
    assert app.test_client().get(f"/shares/{token}").status_code == 404


def test_revoke_requires_login(app, make_share):
    token = make_share("a.txt")
    assert app.test_client().delete(f"/shares/{token}").status_code == 302


def test_expired(app, make_share):
    token = make_share("a.txt", expiry="1d")
    anon = app.test_client()
    assert anon.get(f"/shares/{token}").status_code == 200
    with app.app_context():
        db = get_db()
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.execute("UPDATE shares SET expires_at = ? WHERE token = ?", (past, token))
        db.commit()
    assert anon.get(f"/shares/{token}").status_code == 404


def test_deleted_target(app, data_root, make_share):
    token = make_share("sub")
    shutil.rmtree(data_root / "sub")
    assert app.test_client().get(f"/shares/{token}").status_code == 404


def test_cannot_share_outside_root(auth_client):
    for path in ["../outside", "escape", "sub/escape.txt"]:
        assert auth_client.post("/shares", data={"path": path}).status_code == 404


def test_invalid_expiry(auth_client):
    assert auth_client.post("/shares", data={"path": "a.txt", "expiry": "99y"}).status_code == 400


def test_description(app, make_share):
    token = make_share("a.txt", description="  Tax <b>docs</b>  ")
    page = app.test_client().get(f"/shares/{token}").get_data(as_text=True)
    assert "“Tax &lt;b&gt;docs&lt;/b&gt;”" in page
    plain = make_share("a.txt")
    assert 'class="description"' not in app.test_client().get(f"/shares/{plain}").get_data(as_text=True)


def test_description_too_long(auth_client):
    data = {"path": "a.txt", "expiry": "never", "description": "x" * 129}
    assert auth_client.post("/shares", data=data).status_code == 400


def test_description_column_migrated(app):
    import sqlite3
    from app.db import init_app
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript("DROP TABLE shares; CREATE TABLE shares (token TEXT PRIMARY KEY, rel_path TEXT NOT NULL,"
                     " is_dir INTEGER NOT NULL, created_at TEXT NOT NULL, expires_at TEXT,"
                     " revoked INTEGER NOT NULL DEFAULT 0);")
    db.close()
    init_app(app)
    with app.app_context():
        from app.db import get_db
        assert "description" in {r["name"] for r in get_db().execute("PRAGMA table_info(shares)")}


def test_manage_page(auth_client, make_share):
    token = make_share("sub", expiry="7d")
    page = auth_client.get("/shares").get_data(as_text=True)
    assert token in page and "/sub" in page and "active" in page


def test_public_base_url(app, make_share, auth_client):
    app.config["PUBLIC_BASE_URL"] = "https://files.example.com/"
    token = make_share("a.txt")
    assert f"https://files.example.com/shares/{token}" in auth_client.get("/shares").get_data(as_text=True)


def test_share_dialog(auth_client):
    resp = auth_client.get("/shares/new?path=sub", headers={"HX-Request": "true"})
    assert b"Share folder" in resp.data and b'value="sub"' in resp.data


def test_public_welcome(app, make_share):
    anon = app.test_client()
    file_page = anon.get(f"/shares/{make_share('a.txt')}").get_data(as_text=True)
    assert "Welcome to FroogleDrive, you&#39;ve been shared a file!" in file_page \
        or "Welcome to FroogleDrive, you've been shared a file!" in file_page
    assert "Please choose what you want to do with it below." in file_page
    dir_page = anon.get(f"/shares/{make_share('sub')}").get_data(as_text=True)
    assert "been shared a folder!" in dir_page


@pytest.fixture
def media(data_root):
    (data_root / "sub" / "pic.JPG").write_bytes(b"\xff\xd8fakejpeg")
    (data_root / "sub" / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
    (data_root / "sub" / "page.html").write_text("<script>alert(1)</script>")
    (data_root / "sub" / "logo.svg").write_text("<svg><script>alert(1)</script></svg>")


def test_view_image_inline(app, make_share, media):
    token = make_share("sub/pic.JPG")
    anon = app.test_client()
    assert b"View in browser" in anon.get(f"/shares/{token}").data
    resp = anon.get(f"/shares/{token}?view=1")
    assert resp.mimetype == "image/jpeg"
    assert "attachment" not in resp.headers.get("Content-Disposition", "")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" not in resp.headers


def test_view_pdf_inline(app, make_share, media):
    token = make_share("sub/doc.pdf")
    resp = app.test_client().get(f"/shares/{token}?view=1")
    assert resp.mimetype == "application/pdf"
    assert "attachment" not in resp.headers.get("Content-Disposition", "")
    assert "Content-Security-Policy" not in resp.headers


@pytest.mark.parametrize("name", ["page.html", "logo.svg", "b.txt"])
def test_view_not_allowed_downloads(app, make_share, media, name):
    token = make_share(f"sub/{name}")
    anon = app.test_client()
    assert b"View in browser" not in anon.get(f"/shares/{token}").data
    resp = anon.get(f"/shares/{token}?view=1")
    assert "attachment" in resp.headers["Content-Disposition"]


def test_view_in_folder_share(app, make_share, media):
    token = make_share("sub")
    anon = app.test_client()
    page = anon.get(f"/shares/{token}").get_data(as_text=True)
    assert f"/shares/{token}/pic.JPG?view=1" in page
    assert f"/shares/{token}/page.html?view=1" not in page
    resp = anon.get(f"/shares/{token}/pic.JPG?view=1")
    assert resp.mimetype == "image/jpeg" and "attachment" not in resp.headers.get("Content-Disposition", "")
    assert "attachment" in anon.get(f"/shares/{token}/pic.JPG").headers["Content-Disposition"]


def test_view_video_range(app, make_share, data_root):
    (data_root / "clip.mp4").write_bytes(b"0123456789")
    token = make_share("clip.mp4")
    resp = app.test_client().get(f"/shares/{token}?view=1", headers={"Range": "bytes=2-5"})
    assert resp.status_code == 206 and resp.data == b"2345" and resp.mimetype == "video/mp4"
    assert "Content-Security-Policy" not in resp.headers  # sandbox breaks Chromium's player


def test_public_banner(app, auth_client, make_share):
    app.config["FROOGLEDRIVE_SUBTITLE"] = "Jason's Cloudshare System"
    for path in ["a.txt", "sub"]:
        token = make_share(path)
        # Same banner for anonymous visitors and for the logged-in owner, never any nav
        for client in (app.test_client(), auth_client):
            page = client.get(f"/shares/{token}").get_data(as_text=True)
            assert 'class="topbar"' in page and "Cloudshare System" in page
            assert "Log out" not in page and ">Files<" not in page and ">Shares<" not in page
            assert 'href="/"' not in page and "/login" not in page


def count_shares(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM shares").fetchone()[0]


@pytest.mark.parametrize("parent", ["sub", ""])
def test_cannot_share_folder_containing_share(app, auth_client, make_share, parent):
    make_share("sub/deep/c.txt")
    before = count_shares(app)
    dialog = auth_client.get(f"/shares/new?path={parent}").get_data(as_text=True)
    assert "already contains" in dialog and "/sub/deep/c.txt" in dialog
    assert "Create link" not in dialog
    resp = auth_client.post("/shares", data={"path": parent})
    assert b"already contains" in resp.data
    assert count_shares(app) == before


def test_unrelated_and_inactive_shares_dont_block(app, auth_client, make_share):
    make_share("a.txt")                 # sibling, not inside "sub"
    token = make_share("sub/b.txt")
    auth_client.delete(f"/shares/{token}")  # revoked
    expired = make_share("sub/deep", expiry="1d")
    with app.app_context():
        db = get_db()
        db.execute("UPDATE shares SET expires_at = ? WHERE token = ?",
                   ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), expired))
        db.commit()
    assert b"Create link" in auth_client.get("/shares/new?path=sub").data
    make_share("sub")


def test_prefix_is_path_aware(auth_client, make_share, data_root):
    (data_root / "subway").mkdir()
    (data_root / "subway" / "x.txt").write_text("x")
    make_share("subway/x.txt")          # "subway/" must not count as inside "sub"
    make_share("sub")


def test_delete_revoked(app, auth_client, make_share):
    token = make_share("a.txt")
    assert b"Revoke</button>" in auth_client.get("/shares").data
    assert b"Delete</button>" not in auth_client.get("/shares").data
    assert auth_client.post(f"/shares/{token}/delete").status_code == 409  # still active
    assert app.test_client().get(f"/shares/{token}").status_code == 200

    revoked_row = auth_client.delete(f"/shares/{token}").get_data(as_text=True)
    assert f"/shares/{token}/delete" in revoked_row and "Revoke</button>" not in revoked_row

    resp = auth_client.post(f"/shares/{token}/delete")
    assert resp.status_code == 200 and resp.data == b""
    assert token not in auth_client.get("/shares").get_data(as_text=True)
    assert count_shares(app) == 0
    assert auth_client.post(f"/shares/{token}/delete").status_code == 404


def test_delete_requires_login(app, auth_client, make_share):
    token = make_share("a.txt")
    auth_client.delete(f"/shares/{token}")
    assert app.test_client().post(f"/shares/{token}/delete").status_code == 302
    assert count_shares(app) == 1


def test_file_named_delete_in_folder_share(app, make_share, data_root):
    (data_root / "sub" / "delete").write_text("not a route")
    token = make_share("sub")
    assert app.test_client().get(f"/shares/{token}/delete").data == b"not a route"


def test_revoke_unknown(auth_client):
    assert auth_client.delete("/shares/" + "B" * 32).status_code == 404


def test_target_type_changed(app, data_root, make_share):
    token = make_share("a.txt")
    (data_root / "a.txt").unlink()
    (data_root / "a.txt").mkdir()   # same path, now a folder
    assert app.test_client().get(f"/shares/{token}").status_code == 404
