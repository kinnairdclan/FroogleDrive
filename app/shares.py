import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import (
    Blueprint, Response, abort, current_app, render_template, request, send_file, url_for,
)
from zipstream import ZipStream

from . import fs
from .auth import login_required
from .db import get_db

bp = Blueprint("shares", __name__, url_prefix="/shares")

# Formats browsers display natively, served inline for "View in browser".
# Never add HTML or SVG: they can run scripts on this origin.
VIEWABLE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "avif": "image/avif", "bmp": "image/bmp",
    "mp4": "video/mp4", "m4v": "video/mp4", "webm": "video/webm", "ogv": "video/ogg",
    "pdf": "application/pdf",
}

EXPIRY_CHOICES = {
    "never": ("Never", None),
    "1d": ("1 day", timedelta(days=1)),
    "7d": ("7 days", timedelta(days=7)),
    "30d": ("30 days", timedelta(days=30)),
}

MAX_DESCRIPTION = 128


def _now():
    return datetime.now(timezone.utc)


def share_url(token):
    base = current_app.config.get("PUBLIC_BASE_URL")
    if base:
        return base.rstrip("/") + url_for("shares.public", token=token)
    return url_for("shares.public", token=token, _external=True)


def share_status(row):
    if row["revoked"]:
        return "revoked"
    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= _now():
        return "expired"
    root = current_app.config["FROOGLEDRIVE_ROOT"]
    path = os.path.join(root, row["rel_path"])
    exists = os.path.isdir(path) if row["is_dir"] else os.path.isfile(path)
    return "active" if exists else "missing"


def share_view(row):
    return {
        **dict(row),
        "name": os.path.basename(row["rel_path"])
        or os.path.basename(current_app.config["FROOGLEDRIVE_ROOT"]) or "/",
        "url": share_url(row["token"]),
        "status": share_status(row),
    }


def viewable_type(name):
    """MIME type to display `name` inline with, or None if it's download-only."""
    return VIEWABLE_TYPES.get(os.path.splitext(name)[1].lower().lstrip("."))


@bp.app_template_global()
def viewable(name):
    return viewable_type(name) is not None


def send_shared_file(path):
    """Download `path`, or let the browser display it when ?view=1 and the type allows."""
    mimetype = viewable_type(path) if request.args.get("view") else None
    if mimetype is None:
        return send_file(path, as_attachment=True, conditional=True)
    # The allowlisted type plus nosniff keeps the browser from treating the file
    # as a page. No CSP sandbox: it breaks Chromium's built-in video/PDF viewers.
    resp = send_file(path, mimetype=mimetype, as_attachment=False, conditional=True)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def shares_inside(rel):
    """Active shares strictly inside folder `rel` (a plain path-prefix check)."""
    prefix = rel + os.sep if rel else ""
    rows = get_db().execute("SELECT * FROM shares WHERE revoked = 0").fetchall()
    return [
        r for r in rows
        if r["rel_path"] != rel and r["rel_path"].startswith(prefix) and share_status(r) == "active"
    ]


def share_form(root, target):
    """Render the "create link" dialog, refusing folders that contain active shares."""
    rel = fs.relative(root, target)
    is_dir = os.path.isdir(target)
    nested = shares_inside(rel) if is_dir else []
    return render_template(
        "partials/_share_dialog.html",
        rel=rel,
        name=os.path.basename(target),
        is_dir=is_dir,
        nested=[r["rel_path"] for r in nested],
        expiry_choices=EXPIRY_CHOICES,
        max_description=MAX_DESCRIPTION,
    )


def get_share(token):
    return get_db().execute("SELECT * FROM shares WHERE token = ?", (token,)).fetchone()


# ---- management (login required) -------------------------------------------

@bp.get("")
@login_required
def index():
    rows = get_db().execute("SELECT * FROM shares ORDER BY created_at DESC").fetchall()
    return render_template("shares.html", shares=[share_view(r) for r in rows])


@bp.get("/new")
@login_required
def new():
    root = current_app.config["FROOGLEDRIVE_ROOT"]
    return share_form(root, fs.resolve(root, request.args.get("path", "")))


@bp.post("")
@login_required
def create():
    root = current_app.config["FROOGLEDRIVE_ROOT"]
    target = fs.resolve(root, request.form.get("path", ""))
    expiry = request.form.get("expiry", "never")
    if expiry not in EXPIRY_CHOICES:
        abort(400)
    description = request.form.get("description", "").strip()
    if len(description) > MAX_DESCRIPTION:
        abort(400)
    if os.path.isdir(target) and shares_inside(fs.relative(root, target)):
        return share_form(root, target)  # shows why it can't be shared
    delta = EXPIRY_CHOICES[expiry][1]
    now = _now()
    token = secrets.token_urlsafe(24)
    db = get_db()
    db.execute(
        "INSERT INTO shares (token, rel_path, is_dir, created_at, expires_at, description)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            token,
            fs.relative(root, target),
            int(os.path.isdir(target)),
            now.isoformat(),
            (now + delta).isoformat() if delta else None,
            description or None,
        ),
    )
    db.commit()
    return render_template("partials/_share_dialog.html", share=share_view(get_share(token)))


@bp.delete("/<token:token>")
@login_required
def revoke(token):
    db = get_db()
    db.execute("UPDATE shares SET revoked = 1 WHERE token = ?", (token,))
    db.commit()
    row = get_share(token)
    if row is None:
        abort(404)
    return render_template("partials/_share_row.html", share=share_view(row))


@bp.post("/<token:token>/delete")
@login_required
def delete(token):
    """Remove a revoked share from the list for good. Active links must be revoked first."""
    row = get_share(token)
    if row is None:
        abort(404)
    if not row["revoked"]:
        abort(409)
    db = get_db()
    db.execute("DELETE FROM shares WHERE token = ?", (token,))
    db.commit()
    return ""  # HTMX swaps the row out with nothing


# ---- public (no login) -----------------------------------------------------

def _active_share(token):
    """(row, real_path) for a usable share, otherwise 404 with no detail."""
    row = get_share(token)
    if row is None or share_status(row) != "active":
        abort(404)
    # share_status() has already checked the target exists with the right type
    return row, fs.resolve(current_app.config["FROOGLEDRIVE_ROOT"], row["rel_path"])


@bp.get("/<token:token>", defaults={"sub": ""})
@bp.get("/<token:token>/<path:sub>")
def public(token, sub):
    row, share_root = _active_share(token)
    name = os.path.basename(share_root)

    if not row["is_dir"]:
        if sub:
            abort(404)
        if request.args.get("dl") or request.args.get("view"):
            return send_shared_file(share_root)
        return render_template(
            "public_share.html", public=True, token=token, name=name, is_dir=False,
            size=os.path.getsize(share_root), description=row["description"],
        )

    # Directory share: the shared folder becomes the root for all lookups.
    # Dotfiles (.stversions, .git, .env, ...) are never public, whether named
    # directly or reached through a symlink.
    target = fs.resolve(share_root, sub)
    if fs.is_hidden(sub) or fs.is_hidden(fs.relative(share_root, target)):
        abort(404)
    if os.path.isfile(target):
        return send_shared_file(target)
    rel = fs.relative(share_root, target)
    return render_template(
        "public_share.html", public=True, token=token, name=name, is_dir=True, rel=rel,
        crumbs=fs.breadcrumbs(rel),
        parent=os.path.dirname(rel) if rel else None,
        entries=fs.list_dir(share_root, target, hide_dotfiles=True),
    )


@bp.get("/<token:token>.zip")
def public_zip(token):
    row, share_root = _active_share(token)
    if not row["is_dir"]:
        abort(404)
    zs = ZipStream(sized=True)
    for path, arcname in fs.walk_files(share_root, hide_dotfiles=True):
        zs.add_path(path, arcname)
    filename = (os.path.basename(share_root) or "share") + ".zip"
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "_")
    return Response(
        zs,
        mimetype="application/zip",
        headers={
            "Content-Length": str(len(zs)),
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(filename)}",
        },
    )
