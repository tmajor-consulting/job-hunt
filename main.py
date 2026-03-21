import re
import sys
from datetime import datetime, timezone

from config import REQUIRED_TECH, REQUIRED_TECH_MIN_MATCHES, SEARCH_TERMS
from db import (
    get_connection,
    get_known_ids,
    get_unnotified_jobs,
    init_db,
    insert_jobs,
    log_run,
    mark_notified,
)
from extractor import enrich_job
from notifier import send_heartbeat, send_notification
from scraper import scrape_all_terms


_TITLE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bengineering manager\b",
        r"\bhead of (engineering|software|platform|backend|frontend|product engineering)\b",
        r"\bdirector of engineering\b",
        r"\bvp.{0,5}engineering\b",
        r"\bengineering director\b",
    ]
]


def _title_matches(title: str) -> bool:
    return any(p.search(title) for p in _TITLE_PATTERNS)


_REQUIRED_TECH_PATTERNS = [
    re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
    for t in REQUIRED_TECH
]


def _has_required_tech(job: dict) -> bool:
    desc = job.get("description", "") or ""
    matches = sum(1 for p in _REQUIRED_TECH_PATTERNS if p.search(desc))
    return matches >= REQUIRED_TECH_MIN_MATCHES


def run() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    init_db(conn)

    jobs_found = 0
    jobs_new = 0

    try:
        print(f"[main] Scraping {len(SEARCH_TERMS)} search terms...")
        raw_jobs = scrape_all_terms(SEARCH_TERMS)
        jobs_found = len(raw_jobs)
        print(f"[main] Fetched {jobs_found} total jobs (deduplicated across terms)")

        title_matched = [j for j in raw_jobs if _title_matches(j["title"])]
        print(f"[main] {len(title_matched)} after title filter (was {jobs_found})")

        for job in title_matched:
            enrich_job(job)

        tech_matched = [j for j in title_matched if _has_required_tech(job=j)]
        print(f"[main] {len(tech_matched)} after tech stack filter")

        known_ids = get_known_ids(conn)
        new_jobs = [j for j in tech_matched if j["id"] not in known_ids]
        print(f"[main] {len(new_jobs)} new jobs not seen before")

        jobs_new = insert_jobs(conn, new_jobs)

        unnotified = get_unnotified_jobs(conn)
        print(f"[main] Sending {len(unnotified)} notification(s)...")
        sent = 0
        for row in unnotified:
            job = dict(row)
            if send_notification(job):
                mark_notified(conn, job["id"])
                sent += 1
            else:
                print(f"[main] Telegram failed for job {job['id']} — will retry next run")

        log_run(
            conn,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            status="success",
            error_message=None,
        )
        if sent == 0:
            send_heartbeat(jobs_found)
        print(f"[main] Done. {jobs_new} inserted, {sent} notifications sent.")

    except Exception as e:
        log_run(
            conn,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            status="error",
            error_message=str(e),
        )
        print(f"[main] Fatal error: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
