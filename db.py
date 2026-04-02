import os
import sqlite3
from datetime import date, datetime, timezone

from config import DB_PATH

# ── Base schema ───────────────────────────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);
"""

# ── Migrations ────────────────────────────────────────────────────────────────
# Each entry is (version: int, sql: str). Use plain SQL; leave sql empty ("")
# for bookkeeping-only versions. Versions must be consecutive starting at 1.

_MIGRATIONS: list[tuple[int, str]] = [
    # v1 — baseline: all tables established via DDL above.
    (1, ""),
]


def _run_migrations(conn: sqlite3.Connection) -> None:
    current: int = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ).fetchone()[0]
    for version, sql in _MIGRATIONS:
        if version <= current:
            continue
        if sql.strip():
            conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()
    _run_migrations(conn)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recompute_current_stage(conn: sqlite3.Connection, app_id: int) -> None:
    """Set current_stage and updated_at from the latest event after a mutation."""
    latest = conn.execute(
        "SELECT stage, event_date FROM application_events "
        "WHERE application_id = ? ORDER BY event_date DESC, id DESC LIMIT 1",
        (app_id,),
    ).fetchone()
    if latest:
        conn.execute(
            "UPDATE applications SET current_stage = ?, updated_at = ? WHERE id = ?",
            (latest["stage"], latest["event_date"], app_id),
        )


# ── Scraper / pipeline helpers ────────────────────────────────────────────────

def get_known_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM jobs").fetchall()
    return {r["id"] for r in rows}


def insert_jobs(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    now = _now()
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
    conn.execute("UPDATE jobs SET notified_at = ? WHERE id = ?", (_now(), job_id))
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


# ── Dashboard queries ─────────────────────────────────────────────────────────

def fetch_new_jobs(conn: sqlite3.Connection) -> list[dict]:
    """Return jobs that haven't been dismissed or applied to."""
    rows = conn.execute("""
        SELECT j.id, j.title, j.company, j.location, j.job_url, j.date_posted,
               j.tech_stack, j.company_size, j.is_remote, j.first_seen_at
        FROM jobs j
        WHERE j.dismissed_at IS NULL
          AND j.id NOT IN (SELECT job_id FROM applications WHERE job_id IS NOT NULL)
        ORDER BY j.first_seen_at DESC
    """).fetchall()
    return [dict(r) for r in rows]


def fetch_applications(conn: sqlite3.Connection) -> list[dict]:
    """Return all applications ordered by most recently updated."""
    rows = conn.execute(
        "SELECT id, company, title, job_url, current_stage, applied_at, updated_at, notes "
        "FROM applications ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_events(conn: sqlite3.Connection, app_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, stage, event_date, notes FROM application_events "
        "WHERE application_id = ? ORDER BY event_date ASC, id ASC",
        (app_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Dashboard mutations ───────────────────────────────────────────────────────

def apply_to_job(conn: sqlite3.Connection, job: dict) -> None:
    today = date.today().isoformat()
    cur = conn.execute(
        """INSERT INTO applications (job_id, company, title, job_url, current_stage, applied_at, updated_at)
           VALUES (?, ?, ?, ?, 'cv_sent', ?, ?)""",
        (job["id"], job["company"], job["title"], job.get("job_url"), today, _now()),
    )
    conn.execute(
        "INSERT INTO application_events (application_id, stage, event_date) VALUES (?, 'cv_sent', ?)",
        (cur.lastrowid, today),
    )
    conn.commit()


def add_application(
    conn: sqlite3.Connection,
    company: str,
    title: str,
    job_url: str,
    applied_at: str,
) -> None:
    """Create a manual application (not linked to a scraped job)."""
    cur = conn.execute(
        """INSERT INTO applications (job_id, company, title, job_url, current_stage, applied_at, updated_at)
           VALUES (NULL, ?, ?, ?, 'cv_sent', ?, ?)""",
        (company, title, job_url or None, applied_at, _now()),
    )
    conn.execute(
        "INSERT INTO application_events (application_id, stage, event_date) VALUES (?, 'cv_sent', ?)",
        (cur.lastrowid, applied_at),
    )
    conn.commit()


def dismiss_job(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute("UPDATE jobs SET dismissed_at = ? WHERE id = ?", (_now(), job_id))
    conn.commit()


def add_event(
    conn: sqlite3.Connection,
    app_id: int,
    stage: str,
    event_date: str,
    notes: str,
) -> None:
    conn.execute(
        "INSERT INTO application_events (application_id, stage, event_date, notes) VALUES (?, ?, ?, ?)",
        (app_id, stage, event_date, notes or None),
    )
    conn.execute(
        "UPDATE applications SET current_stage = ?, updated_at = ? WHERE id = ?",
        (stage, event_date, app_id),
    )
    conn.commit()


def update_event(
    conn: sqlite3.Connection,
    event_id: int,
    app_id: int,
    stage: str,
    event_date: str,
    notes: str,
) -> None:
    conn.execute(
        "UPDATE application_events SET stage = ?, event_date = ?, notes = ? WHERE id = ?",
        (stage, event_date, notes or None, event_id),
    )
    _recompute_current_stage(conn, app_id)
    conn.commit()


def delete_event(conn: sqlite3.Connection, event_id: int, app_id: int) -> None:
    conn.execute("DELETE FROM application_events WHERE id = ?", (event_id,))
    _recompute_current_stage(conn, app_id)
    conn.commit()


def delete_application(conn: sqlite3.Connection, app_id: int) -> None:
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
