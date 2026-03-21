# job-hunt

A personal job-hunt automation tool for Engineering Manager / Head of Engineering roles. Scrapes LinkedIn daily, filters by title and tech stack, sends Telegram notifications for new listings, and provides a local dashboard to track your applications through the interview process.

## Features

- **Daily LinkedIn scraper** — searches for EM / Head of Engineering / Director of Engineering roles in a configurable location
- **Smart filtering** — title regex whitelist + tech stack keyword matching (configurable minimum overlap)
- **Telegram notifications** — one message per new job, plus a daily heartbeat when nothing new is found
- **Local dashboard** — Streamlit app for tracking applications, interview stages, and a full timeline of events
- **One-command setup** — `setup.sh` handles venv detection, Doppler config, plist generation, and launchd registration

## Requirements

- macOS (launchd scheduling)
- Python 3.11+
- [Doppler CLI](https://docs.doppler.com/docs/install-cli) for secrets management
- A Telegram bot (see setup below)

## Quick start

```bash
# 1. Clone and install dependencies
git clone <repo-url> job-hunt
cd job-hunt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure secrets in Doppler (see below)

# 3. Run setup — configures Doppler and registers the daily schedule
./setup.sh

# 4. Test it
launchctl start com.$(whoami).jobhunt
tail -f data/launchd.log
```

## Doppler setup

Secrets are managed via [Doppler](https://doppler.com) (free tier is sufficient).

```bash
# Create a project called "job-hunt" in the Doppler dashboard, then:
doppler setup --project job-hunt --config dev

# Set required secrets
doppler secrets set TELEGRAM_BOT_TOKEN="your_token"
doppler secrets set TELEGRAM_CHAT_ID="your_chat_id"
```

Optional overrides (have sensible defaults):
```bash
doppler secrets set DB_PATH="data/jobs.db"
doppler secrets set RESULTS_PER_SEARCH="200"
doppler secrets set SCRAPE_DELAY_SECONDS="3.0"
```

### Creating a Telegram bot

1. Open Telegram → search **@BotFather** → `/newbot` → follow prompts → copy the token
2. Send any message to your new bot
3. Get your chat ID:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   Look for `"id"` inside the `"chat"` object in the response

## Configuration

All search behaviour lives in `config.py`:

```python
# Job titles to search for on LinkedIn
SEARCH_TERMS = [
    "Engineering Manager",
    "Head of Engineering",
    "Director of Engineering",
]

# Location
SEARCH_LOCATION = "Munich, Germany"

# Tech stack filter — job description must mention at least
# REQUIRED_TECH_MIN_MATCHES of these terms
REQUIRED_TECH = [
    "TypeScript", "JavaScript", "Node.js", "NestJS",
    "React", "microservices", "event-driven", "Kafka",
]
REQUIRED_TECH_MIN_MATCHES = 2
```

The title filter (in `main.py`) accepts: Engineering Manager, Head of Engineering/Software/Platform/Backend/Frontend, Director of Engineering, VP Engineering, Engineering Director.

## Running the scraper manually

```bash
doppler run -- python3 main.py
```

Example output:
```
[main] Scraping 3 search terms...
[main] Fetched 173 total jobs (deduplicated across terms)
[main] 34 after title filter (was 173)
[main] 6 after tech stack filter
[main] 2 new jobs not seen before
[main] Sending 2 notification(s)...
[main] Done. 2 inserted, 2 notifications sent.
```

### Telegram notification format

```
*Engineering Manager*
🏢 Acme Corp

📍 Munich, Bavaria  |  On-site / Hybrid
👔 1001-5000  |  Full Time
📅 Posted: 2026-03-19

🛠 Tech: Kafka, NestJS, TypeScript

🔗 Apply here
```

## Dashboard

```bash
streamlit run dashboard.py
```

Opens at `http://localhost:8501`.

**Applications tab** — metrics, filterable list, inline timeline per application, stage updates
**New Jobs tab** — scraped jobs not yet acted on; click "Applied" to move to tracker or "Dismiss" to hide

### Interview stages

| Stage | Label |
|---|---|
| `cv_sent` | 📤 CV Sent |
| `phone_screen` | 📞 Phone Screen |
| `round_1` | 🔵 Round 1 |
| `round_2` | 🔵 Round 2 |
| `round_3` | 🔵 Round 3 |
| `offer` | 🎉 Offer |
| `offer_accepted` | ✅ Accepted |
| `offer_declined` | 🚫 Declined Offer |
| `rejected_cv` | ❌ Rejected (CV) |
| `rejected_later` | ❌ Rejected (Later) |
| `withdrawn` | ↩️ Withdrawn |

## File structure

```
job-hunt/
├── main.py              # Scraper entry point
├── scraper.py           # LinkedIn scraping via jobspy
├── extractor.py         # Tech stack extraction from descriptions
├── notifier.py          # Telegram notifications + heartbeat
├── db.py                # SQLite schema and helpers
├── config.py            # Search terms, tech filters, constants
├── dashboard.py         # Streamlit application tracker
├── setup.sh             # One-command setup for scheduling
├── requirements.txt
└── data/                # Created at runtime (gitignored)
    ├── jobs.db          # SQLite database
    └── launchd.log      # Scraper run logs
```

## Database

Single SQLite file at `data/jobs.db`. Four tables:

| Table | Purpose |
|---|---|
| `jobs` | All scraped LinkedIn listings |
| `runs` | Scraper run history |
| `applications` | Jobs applied to with current stage |
| `application_events` | Full stage history with dates and notes |

Install the **SQLite Viewer** VS Code extension (search: `sqlite viewer`) to browse it visually.

### Useful commands

```bash
# Inspect jobs
sqlite3 data/jobs.db "SELECT title, company, tech_stack FROM jobs LIMIT 10;"

# Clear scraped jobs (re-fetches everything on next run)
sqlite3 data/jobs.db "DELETE FROM jobs;"

# Clear applications
sqlite3 data/jobs.db "DELETE FROM applications;"
```

## Scheduling

`setup.sh` registers a launchd agent that runs daily at 8:30 AM. If the Mac is asleep at that time, it fires the next time the machine wakes.

```bash
# Trigger manually
launchctl start com.$(whoami).jobhunt

# Disable
launchctl unload ~/Library/LaunchAgents/com.$(whoami).jobhunt.plist

# View logs
tail -f data/launchd.log
```

> **Note:** Requires the screen to be locked, not logged out (`Cmd+Ctrl+Q`). Logging out (`Cmd+Shift+Q`) terminates the user session and prevents launchd agents from running.
