import json
import os
from datetime import date

import requests

_ESCAPE_CHARS = r"\_*[]()~`>#+-=|{}.!"

# One session for the lifetime of the process — reuses TCP connections across a batch.
_session = requests.Session()


def _api_url() -> str:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    return f"https://api.telegram.org/bot{token}/sendMessage"


def _chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]


def _esc(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    for ch in _ESCAPE_CHARS:
        text = text.replace(ch, f"\\{ch}")
    return text


def format_message(job: dict) -> str:
    title = _esc(job.get("title", "") or "Unknown Title")
    company = _esc(job.get("company", "") or "Unknown Company")
    location = _esc(job.get("location", "") or "—")
    job_url = job.get("job_url", "") or ""
    date_posted = _esc(str(job.get("date_posted", "") or "—"))
    emp_type = _esc((job.get("employment_type", "") or "").replace("_", " ").title())
    company_size = _esc(job.get("company_size", "") or "—")

    is_remote = job.get("is_remote")
    remote_str = _esc("Remote" if is_remote else "On\\-site / Hybrid")

    tech_list = json.loads(job.get("tech_stack") or "[]")
    tech_str = _esc(", ".join(tech_list) if tech_list else "—")

    lines = [
        f"*{title}*",
        f"🏢 {company}",
        "",
        f"📍 {location}  \\|  {remote_str}",
        f"👔 {company_size}  \\|  {emp_type}",
        f"📅 Posted: {date_posted}",
        "",
        f"🛠 Tech: {tech_str}",
        "",
        f"🔗 [Apply here]({job_url})",
    ]
    return "\n".join(lines)


def send_heartbeat(jobs_checked: int) -> bool:
    text = (
        f"✅ Scraper ran — no new jobs today\\.\n"
        f"📊 {jobs_checked} listings checked · {_esc(date.today().isoformat())}"
    )
    try:
        resp = _session.post(
            _api_url(),
            json={
                "chat_id": _chat_id(),
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def send_notification(job: dict) -> bool:
    text = format_message(job)
    try:
        resp = _session.post(
            _api_url(),
            json={
                "chat_id": _chat_id(),
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[notifier] Telegram error {resp.status_code}: {resp.text}")
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"[notifier] Request failed: {e}")
        return False
