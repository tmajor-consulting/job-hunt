import os
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    job_url           TEXT UNIQUE NOT NULL,
    title             TEXT,
    company           TEXT,
    location          TEXT,
    date_posted       TEXT,
    employment_type   TEXT,
    is_remote         INTEGER,
    work_model        TEXT,
    salary_min        REAL,
    salary_max        REAL,
    salary_currency   TEXT,
    company_size      TEXT,
    description       TEXT,
    tech_stack        TEXT,
    team_size_signals TEXT,
    first_seen_at     TEXT NOT NULL,
    notified_at       TEXT,
    dismissed_at      TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    jobs_found    INTEGER,
    jobs_new      INTEGER,
    status        TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_notified   ON jobs(notified_at);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at);

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT REFERENCES jobs(id),
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    job_url         TEXT,
    current_stage   TEXT NOT NULL DEFAULT 'cv_sent',
    applied_at      TEXT,
    updated_at      TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS application_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL,
    event_date      TEXT NOT NULL,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_app ON application_events(application_id);
"""


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def get_known_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM jobs").fetchall()
    return {r["id"] for r in rows}


def insert_jobs(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for job in jobs:
        try:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, job_url, title, company, location, date_posted,
                    employment_type, is_remote, work_model,
                    salary_min, salary_max, salary_currency,
                    company_size, description, tech_stack, team_size_signals,
                    first_seen_at, notified_at
                ) VALUES (
                    :id, :job_url, :title, :company, :location, :date_posted,
                    :employment_type, :is_remote, :work_model,
                    :salary_min, :salary_max, :salary_currency,
                    :company_size, :description, :tech_stack, :team_size_signals,
                    :first_seen_at, NULL
                )
                """,
                {**job, "first_seen_at": now},
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def get_unnotified_jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM jobs WHERE notified_at IS NULL ORDER BY first_seen_at ASC"
    ).fetchall()


def mark_notified(conn: sqlite3.Connection, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE jobs SET notified_at = ? WHERE id = ?", (now, job_id))
    conn.commit()


def log_run(
    conn: sqlite3.Connection,
    started_at: str,
    finished_at: str,
    jobs_found: int,
    jobs_new: int,
    status: str,
    error_message: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO runs (started_at, finished_at, jobs_found, jobs_new, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (started_at, finished_at, jobs_found, jobs_new, status, error_message),
    )
    conn.commit()
