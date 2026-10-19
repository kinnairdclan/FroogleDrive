import os
from datetime import timedelta


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config():
    """Build the Flask config dict from environment variables."""
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "FROOGLEDRIVE_ROOT": os.environ.get("FROOGLEDRIVE_ROOT", "/data"),
        "FROOGLEDRIVE_USERNAME": os.environ.get("FROOGLEDRIVE_USERNAME"),
        "FROOGLEDRIVE_PASSWORD_HASH": os.environ.get("FROOGLEDRIVE_PASSWORD_HASH"),
        # Optional text shown in parentheses after the name in the header
        "FROOGLEDRIVE_SUBTITLE": os.environ.get("FROOGLEDRIVE_SUBTITLE", ""),
        # e.g. https://files.example.com, used to build absolute share links
        "PUBLIC_BASE_URL": os.environ.get("PUBLIC_BASE_URL") or None,
        "DATABASE": os.environ.get("DATABASE"),  # defaults to <instance>/shares.db
        # Number of reverse proxies in front of the app (0 = trust no X-Forwarded-* headers)
        "TRUST_PROXY": int(os.environ.get("FROOGLEDRIVE_TRUST_PROXY") or 0),
        "SESSION_COOKIE_SECURE": _bool("FROOGLEDRIVE_SECURE_COOKIES"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(days=7),
        "WTF_CSRF_TIME_LIMIT": None,  # token lives as long as the session
    }
