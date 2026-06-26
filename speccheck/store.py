"""SQLite persistence for completed reviews.

Keeps an audit trail so a reviewer can pull up past submittal decisions for a
project section — useful when a contractor resubmits and you need to confirm
which findings were cleared. The web app stores the full spec and submittal
text alongside each review so a resubmittal can be diffed against a prior round
and a saved review can be re-opened.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Report
from .report import to_dict

DEFAULT_DB = Path("speccheck.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project         TEXT NOT NULL DEFAULT '',
    section         TEXT NOT NULL,
    compliant       INTEGER NOT NULL,
    summary         TEXT NOT NULL,
    findings        TEXT NOT NULL,
    spec_text       TEXT NOT NULL DEFAULT '',
    submittal_text  TEXT NOT NULL DEFAULT '',
    prior_id        INTEGER,
    created_at      TEXT NOT NULL
);
"""

# (column, definition) pairs added to databases created by older versions.
_MIGRATIONS = [
    ("project", "TEXT NOT NULL DEFAULT ''"),
    ("spec_text", "TEXT NOT NULL DEFAULT ''"),
    ("submittal_text", "TEXT NOT NULL DEFAULT ''"),
    ("prior_id", "INTEGER"),
]


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute(_SCHEMA)
    _migrate(conn)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(reviews)")}
    for column, ddl in _MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE reviews ADD COLUMN {column} {ddl}")
    conn.commit()


def save_review(
    report: Report,
    db_path: str | Path = DEFAULT_DB,
    *,
    project: str = "",
    spec_text: str = "",
    submittal_text: str = "",
    prior_id: int | None = None,
) -> int:
    """Persist a review and return its id.

    The optional fields let the web app keep the originating project name,
    documents, and a link to the prior review this one supersedes.
    """
    data = to_dict(report)
    conn = connect(db_path)
    with conn:
        cur = conn.execute(
            "INSERT INTO reviews"
            " (project, section, compliant, summary, findings,"
            "  spec_text, submittal_text, prior_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project,
                report.section,
                int(report.compliant),
                json.dumps(data["summary"]),
                json.dumps(data["findings"]),
                spec_text,
                submittal_text,
                prior_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    review_id = cur.lastrowid
    conn.close()
    return review_id


def list_reviews(db_path: str | Path = DEFAULT_DB) -> list[dict]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT id, project, section, compliant, summary, prior_id, created_at"
        " FROM reviews ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_review(review_id: int, db_path: str | Path = DEFAULT_DB) -> dict | None:
    """Return a saved review (with findings and documents) or None."""
    conn = connect(db_path)
    row = conn.execute(
        "SELECT id, project, section, compliant, summary, findings,"
        " spec_text, submittal_text, prior_id, created_at"
        " FROM reviews WHERE id = ?",
        (review_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    data = dict(row)
    data["summary"] = json.loads(data["summary"])
    data["findings"] = json.loads(data["findings"])
    return data
