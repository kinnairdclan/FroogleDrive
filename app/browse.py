import os

from flask import Blueprint, current_app, redirect, render_template, request, send_file, url_for

from . import fs
from .auth import login_required

bp = Blueprint("browse", __name__)


def is_partial_request():
    """HTMX swap request, as opposed to a full page load or history restore."""
    return bool(request.headers.get("HX-Request")) and not request.headers.get(
        "HX-History-Restore-Request"
    )


@bp.get("/")
@login_required
def index():
    return redirect(url_for("browse.browse"))


@bp.get("/browse/", defaults={"rel": ""})
@bp.get("/browse/<path:rel>")
@login_required
def browse(rel):
    root = current_app.config["FROOGLEDRIVE_ROOT"]
    target = fs.resolve(root, rel)
    if os.path.isfile(target):
        return send_file(target, as_attachment=True, conditional=True)

    rel = fs.relative(root, target)
    context = {
        "rel": rel,
        "entries": fs.list_dir(root, target),
        "crumbs": fs.breadcrumbs(rel),
        "parent": os.path.dirname(rel) if rel else None,
    }
    template = "partials/_listing.html" if is_partial_request() else "browse.html"
    return render_template(template, **context)
