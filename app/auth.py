import functools
import hmac
import threading
import time

from flask import (
    Blueprint, current_app, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash

bp = Blueprint("auth", __name__)

MAX_FAILURES = 5
LOCKOUT_SECONDS = 300

# Per-process failed-login tracker: ip -> [timestamps]
_failures = {}
_failures_lock = threading.Lock()


def _recent_failures(ip, now):
    with _failures_lock:
        attempts = [t for t in _failures.get(ip, []) if now - t < LOCKOUT_SECONDS]
        _failures[ip] = attempts
        return len(attempts)


def _record_failure(ip, now):
    with _failures_lock:
        _failures.setdefault(ip, []).append(now)


def _safe_next(target):
    # Only allow local paths, never "//host" or absolute URLs
    if target and target.startswith("/") and not target.startswith(("//", "/\\")):
        return target
    return url_for("browse.index")


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user"):
            return view(*args, **kwargs)
        login_url = url_for("auth.login", next=request.full_path.rstrip("?"))
        if request.headers.get("HX-Request"):
            return "", 401, {"HX-Redirect": login_url}
        return redirect(login_url)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        now = time.monotonic()
        if _recent_failures(ip, now) >= MAX_FAILURES:
            error = "Too many failed attempts. Try again in a few minutes."
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user_ok = hmac.compare_digest(
                username.encode(), current_app.config["FROOGLEDRIVE_USERNAME"].encode()
            )
            pw_ok = check_password_hash(current_app.config["FROOGLEDRIVE_PASSWORD_HASH"], password)
            if user_ok and pw_ok:
                session.clear()
                session.permanent = True
                session["user"] = username
                return redirect(_safe_next(request.args.get("next")))
            _record_failure(ip, now)
            error = "Invalid username or password."
    return render_template("login.html", error=error), 401 if error else 200


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
