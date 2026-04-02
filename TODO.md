# Job Hunt — Audit TODO

## Fix Now
- [x] **#1 XSS** — user notes and LinkedIn-scraped fields (title, company, location, tech) injected raw into `unsafe_allow_html` strings; escape all dynamic values with `html.escape()`
- [x] **#2 Foreign keys not enforced** — `PRAGMA foreign_keys = ON` missing; `ON DELETE CASCADE` on `application_events` is silently ignored, leaving orphaned rows when an application is deleted
- [x] **#24 Timeline sort is non-deterministic** — `ORDER BY event_date ASC` has no tiebreaker; two events on the same date appear in arbitrary order; add `id ASC` as secondary sort (also fix the `DESC` variant in `update_event`/`delete_event`)
- [x] **#20 Delete step has no confirmation** — clicking 🗑 immediately destroys a timeline event; add a two-stage confirm (🗑 → ✓ / ✗) via session state

## Fix Soon
- [x] **#3 Module-level secret crash** — `_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]` in `notifier.py` raises `KeyError` at import time if Doppler is not active; move to lazy access inside each function
- [x] **#6 SQL in the UI layer** — 8 DB functions live in `dashboard.py`; move all SQL to `db.py` and import them; the UI should have zero knowledge of table structure
- [x] **#15 No migration system** — `CREATE TABLE IF NOT EXISTS` cannot add columns; add a `schema_version` table with sequential migration functions, or adopt Alembic
- [x] **#21 No manual application entry** — no way to track jobs applied to outside the scraper (referrals, company career pages); add an "Add manually" form to the Applications tab
- [x] **#13 Unpinned dependencies** — `python-jobspy>=0.1.0` allows any future breaking version; pin to known-good minor versions (`~=x.y.z`) and commit a `requirements.lock` or use `pip-tools`

## Clean Up
- [ ] **#7 Dead columns** — `work_model` and `team_size_signals` are always `None` in both schema and `_normalize_row`; remove or populate them
- [ ] **#8 Mixed timestamp formats** — `updated_at` stores a full UTC ISO timestamp while `applied_at` and `event_date` store bare date strings (`YYYY-MM-DD`); the dashboard slices with `[:10]` to compensate; standardise on one format throughout
- [ ] **#9 `_esc()` is O(n·m)** — 13 sequential `str.replace` calls in `notifier.py`; replace with a single compiled `re.sub`: `re.compile(r'([_*\[\]()~\`>#+=|{}.!\\-])').sub(r'\\\1', text)`
- [ ] **#10 No `requests.Session`** — each `send_notification` call opens a new TCP connection; use a module-level `Session` for connection reuse across a batch
- [ ] **#11 Print-based logging** — `print(f"[main] ...")` throughout; replace with the `logging` module for levels, timestamps, and structured output to the launchd log file
- [ ] **#19 Committed plist has hardcoded paths** — `com.tamas.jobhunt.plist` contains `/Users/tamas/...` absolute paths making it non-portable; `setup.sh` generates the correct one, so add the static file to `.gitignore`

## Nice to Have
- [ ] **#5 Truncated SHA-256 ID** — `_make_id` takes only 16 hex chars (64-bit); collision probability is negligible for personal use but consider using the full hash or a UUID
- [ ] **#12 `get_known_ids` full table scan** — loads all job IDs into memory; replace with `INSERT OR IGNORE INTO jobs ...` and check `conn.changes()` to count insertions; eliminates `get_known_ids` entirely
- [ ] **#14 Double description scan** — `enrich_job` and `_has_required_tech` both regex-scan the raw description independently with different keyword lists; document the intent or unify the passes
- [ ] **#16 Cached DB connection ignores external changes** — `@st.cache_resource` holds the connection forever; add a "↻ Refresh" button that calls `st.cache_resource.clear()` or use a `ttl=` parameter
- [ ] **#17 No Telegram retry/backoff** — if Telegram is down, all queued jobs fire as a burst on the next run; add exponential backoff or a `retry_count` column
- [ ] **#18 Scraper errors log as success** — if every search term fails, `jobs_found=0`, `jobs_new=0`, `status="success"`, and a heartbeat fires; distinguish "ran cleanly with no results" from "had errors"
- [ ] **#22 No step count on application rows** — impossible to see at a glance whether an application has 1 step or 8 without opening it; add a small badge to each row
- [ ] **#23 No sort control** — applications are always sorted by `updated_at DESC`; add a toggle for `applied_at ASC` to review applications chronologically
- [ ] **#25 "Updated" date is logical, not wall-clock** — if you backfill a past event the "Updated" column goes backwards; store a separate `last_modified_at` wall-clock timestamp and display that
- [ ] **#26 Empty timeline has no message** — if all events are deleted, the Timeline section disappears silently; show "No steps logged yet"
- [ ] **#27 Inconsistent feedback** — `add_event` shows a toast; `update_event` silently reruns; add a toast to the edit save path too
- [ ] **#28 No export** — no way to back up or analyse application data externally; add a `st.download_button` that exports the applications + events as CSV
