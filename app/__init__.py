import os
from datetime import datetime

from flask import Flask, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

from . import db
from .config import load_config
from .icons import icon_name

csrf = CSRFProtect()

REQUIRED_SETTINGS = ("SECRET_KEY", "FROOGLEDRIVE_USERNAME", "FROOGLEDRIVE_PASSWORD_HASH")
MIN_SECRET_KEY_LENGTH = 32
EXAMPLE_SECRET_KEY = "change-me-to-a-long-random-string"  # shipped in older .env.example

CSP = (
    "default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


class TokenConverter(BaseConverter):
    """Matches share tokens: secrets.token_urlsafe(24) -> 32 URL-safe chars."""

    regex = r"[A-Za-z0-9_-]{32}"


def create_app(test_config=None, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.update(load_config())
    if test_config:
        app.config.update(test_config)

    missing = [key for key in REQUIRED_SETTINGS if not app.config.get(key)]
    if missing:
        raise RuntimeError(
            "Missing required settings: " + ", ".join(missing)
            + ". Generate a password hash with: python -m app.hash_password"
        )
    # Anyone who knows or guesses the key can forge a logged-in session cookie
    key = app.config["SECRET_KEY"]
    if len(key) < MIN_SECRET_KEY_LENGTH or key == EXAMPLE_SECRET_KEY:
        raise RuntimeError(
            f"SECRET_KEY must be a random string of at least {MIN_SECRET_KEY_LENGTH} characters."
            " Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = os.path.join(app.instance_path, "shares.db")
    app.config["FROOGLEDRIVE_ROOT"] = os.path.realpath(app.config["FROOGLEDRIVE_ROOT"])

    if app.config["TRUST_PROXY"]:
        n = app.config["TRUST_PROXY"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n, x_prefix=n)

    app.url_map.converters["token"] = TokenConverter
    csrf.init_app(app)
    db.init_app(app)

    from . import auth, browse, shares

    app.register_blueprint(auth.bp)
    app.register_blueprint(browse.bp)
    app.register_blueprint(shares.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        # same-origin, not no-referrer: share tokens live in URLs, but Flask-WTF
        # rejects HTTPS form posts that carry no same-origin Referer
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if resp.mimetype == "text/html":
            # Pages only; inline-viewed files keep none so browser PDF/video viewers work
            resp.headers.setdefault("Content-Security-Policy", CSP)
        if app.config.get("SESSION_COOKIE_SECURE"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return resp

    @app.context_processor
    def brand():
        # Accept the subtitle with or without its own surrounding parentheses
        subtitle = (app.config.get("FROOGLEDRIVE_SUBTITLE") or "").strip()
        if subtitle.startswith("(") and subtitle.endswith(")"):
            subtitle = subtitle[1:-1].strip()
        return {"brand_subtitle": subtitle}

    @app.template_global()
    def file_icon(name, is_dir=False):
        return url_for("static", filename=f"icons/{icon_name(name, is_dir)}.svg")

    @app.template_global()
    def split_name(name, is_dir=False):
        """(stem, extension); folders keep their whole name as the stem."""
        return (name, "") if is_dir else os.path.splitext(name)

    @app.template_filter("filesize")
    def filesize(num):
        if num < 1024:
            return f"{num} B"
        for unit in ("KB", "MB", "GB"):
            num /= 1024
            if num < 1024:
                return f"{num:.1f} {unit}"
        return f"{num / 1024:.1f} TB"

    @app.template_filter("datetime")
    def format_datetime(value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            value = datetime.fromtimestamp(value)
        elif isinstance(value, str):
            value = datetime.fromisoformat(value).astimezone()
        return value.strftime("%Y-%m-%d %H:%M")

    return app
