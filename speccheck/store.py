"""Lightweight SQLite persistence for completed reviews.

Keeps an audit trail so a reviewer can pull up past submittal decisions for a
project section — useful when a contractor resubmits and you need to confirm
which findings were cleared.
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
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section     TEXT NOT NULL,
    compliant   INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    findings    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute(_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def save_review(report: Report, db_path: str | Path = DEFAULT_DB) -> int:
    data = to_dict(report)
    conn = connect(db_path)
    with conn:
        cur = conn.execute(
            "INSERT INTO reviews (section, compliant, summary, findings, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                report.section,
                int(report.compliant),
                json.dumps(data["summary"]),
                json.dumps(data["findings"]),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    review_id = cur.lastrowid
    conn.close()
    return review_id


def list_reviews(db_path: str | Path = DEFAULT_DB) -> list[dict]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT id, section, compliant, summary, created_at"
        " FROM reviews ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_review(review_id: int, db_path: str | Path = DEFAULT_DB) -> dict | None:
    """Return a saved review (with its findings) or None if not found."""
    conn = connect(db_path)
    row = conn.execute(
        "SELECT id, section, compliant, summary, findings, created_at"
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
