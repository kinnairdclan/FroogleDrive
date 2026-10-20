import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS shares (
    token      TEXT PRIMARY KEY,
    rel_path   TEXT NOT NULL,
    is_dir     INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    revoked    INTEGER NOT NULL DEFAULT 0,
    description TEXT
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        # Databases created before descriptions existed lack the column
        columns = {row["name"] for row in db.execute("PRAGMA table_info(shares)")}
        if "description" not in columns:
            db.execute("ALTER TABLE shares ADD COLUMN description TEXT")
            db.commit()
