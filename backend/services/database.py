"""SQLite storage for trials and (optionally) cached patient analyses.

Uses plain sqlite3 with a thin repository layer so it is trivial to swap for
PostgreSQL later: only this module touches SQL.
"""
import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from config import DATA_DIR
from models import Trial

DB_PATH = DATA_DIR / "ctq.db"

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trials (
                trial_id      TEXT PRIMARY KEY,
                title         TEXT NOT NULL,
                condition     TEXT NOT NULL,
                status        TEXT,
                phase         TEXT,
                study_type    TEXT,
                gender        TEXT,
                min_age       REAL,
                max_age       REAL,
                inclusion     TEXT,   -- JSON array
                exclusion     TEXT,   -- JSON array
                locations     TEXT,   -- JSON array
                sponsor       TEXT,
                interventions TEXT,   -- JSON array
                source        TEXT,
                last_updated  TEXT
            );

            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT DEFAULT (datetime('now')),
                metrics     TEXT NOT NULL,   -- JSON
                detail      TEXT NOT NULL    -- JSON rows
            );
            """
        )


# ---------------------------------------------------------------------------
# Trials
# ---------------------------------------------------------------------------

def _trial_from_row(row: sqlite3.Row) -> Trial:
    return Trial(
        trial_id=row["trial_id"],
        title=row["title"],
        condition=row["condition"],
        status=row["status"] or "Unknown",
        phase=row["phase"] or "N/A",
        study_type=row["study_type"] or "Interventional",
        gender=row["gender"] or "Both",
        min_age=row["min_age"],
        max_age=row["max_age"],
        inclusion_criteria=json.loads(row["inclusion"] or "[]"),
        exclusion_criteria=json.loads(row["exclusion"] or "[]"),
        locations=json.loads(row["locations"] or "[]"),
        sponsor=row["sponsor"],
        interventions=json.loads(row["interventions"] or "[]"),
        source=row["source"] or "CTRI",
        last_updated=row["last_updated"],
    )


def upsert_trials(trials: List[Trial]) -> int:
    """Insert or update trials; returns the number written."""
    if not trials:
        return 0
    with _lock, _connect() as conn:
        conn.executemany(
            """
            INSERT INTO trials (trial_id, title, condition, status, phase, study_type,
                                gender, min_age, max_age, inclusion, exclusion,
                                locations, sponsor, interventions, source, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(trial_id) DO UPDATE SET
                title=excluded.title, condition=excluded.condition,
                status=excluded.status, phase=excluded.phase,
                study_type=excluded.study_type, gender=excluded.gender,
                min_age=excluded.min_age, max_age=excluded.max_age,
                inclusion=excluded.inclusion, exclusion=excluded.exclusion,
                locations=excluded.locations, sponsor=excluded.sponsor,
                interventions=excluded.interventions, source=excluded.source,
                last_updated=excluded.last_updated
            """,
            [
                (
                    t.trial_id, t.title, t.condition, t.status, t.phase, t.study_type,
                    t.gender, t.min_age, t.max_age,
                    json.dumps(t.inclusion_criteria), json.dumps(t.exclusion_criteria),
                    json.dumps(t.locations), t.sponsor, json.dumps(t.interventions),
                    t.source, t.last_updated,
                )
                for t in trials
            ],
        )
    return len(trials)


def get_all_trials() -> List[Trial]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM trials ORDER BY trial_id").fetchall()
    return [_trial_from_row(r) for r in rows]


def get_trial(trial_id: str) -> Optional[Trial]:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM trials WHERE trial_id = ?", (trial_id,)).fetchone()
    return _trial_from_row(row) if row else None


def trial_count() -> int:
    with _lock, _connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM trials").fetchone()
    return n


# ---------------------------------------------------------------------------
# Evaluation run history
# ---------------------------------------------------------------------------

def save_evaluation_run(metrics: dict, rows: list) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_runs (metrics, detail) VALUES (?, ?)",
            (json.dumps(metrics), json.dumps(rows)),
        )
        return cur.lastrowid


def list_evaluation_runs(limit: int = 10) -> list:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, metrics FROM evaluation_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"id": r["id"], "created_at": r["created_at"], "metrics": json.loads(r["metrics"])} for r in rows]
