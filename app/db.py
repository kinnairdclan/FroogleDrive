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
    description TEXT,
    hits       INTEGER NOT NULL DEFAULT 0
);
"""

MIGRATIONS = [
    ("description", "TEXT"),
    ("hits", "INTEGER NOT NULL DEFAULT 0"),
]


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
        # Databases created before these columns existed lack them
        columns = {row["name"] for row in db.execute("PRAGMA table_info(shares)")}
        for name, decl in MIGRATIONS:
            if name not in columns:
                db.execute(f"ALTER TABLE shares ADD COLUMN {name} {decl}")
        db.commit()
