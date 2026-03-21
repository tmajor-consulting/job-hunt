import json
import os
import requests

_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
_API_URL = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"

_ESCAPE_CHARS = r"\_*[]()~`>#+-=|{}.!"


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
    from datetime import date
    text = (
        f"✅ Scraper ran — no new jobs today\\.\n"
        f"📊 {jobs_checked} listings checked · {_esc(date.today().isoformat())}"
    )
    try:
        resp = requests.post(
            _API_URL,
            json={
                "chat_id": _CHAT_ID,
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
        resp = requests.post(
            _API_URL,
            json={
                "chat_id": _CHAT_ID,
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
