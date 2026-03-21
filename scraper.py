import hashlib
import time

import pandas as pd
from jobspy import scrape_jobs

from config import RESULTS_PER_SEARCH, SCRAPE_DELAY_SECONDS, SEARCH_LOCATION


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _str(val) -> str:
    return str(val) if val is not None and not (isinstance(val, float) and pd.isna(val)) else ""


def _float_or_none(val) -> float | None:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _normalize_row(row: pd.Series) -> dict:
    url = _str(row.get("job_url"))
    return {
        "id": _make_id(url),
        "job_url": url,
        "title": _str(row.get("title")),
        "company": _str(row.get("company")),
        "location": _str(row.get("location")),
        "date_posted": _str(row.get("date_posted")),
        "employment_type": _str(row.get("job_type")),
        "is_remote": int(bool(row.get("is_remote"))),
        "work_model": None,
        "salary_min": _float_or_none(row.get("min_amount")),
        "salary_max": _float_or_none(row.get("max_amount")),
        "salary_currency": _str(row.get("currency")),
        "company_size": _str(row.get("company_num_employees")),
        "description": _str(row.get("description")),
        "tech_stack": None,
        "team_size_signals": None,
    }


def scrape_all_terms(search_terms: list[str]) -> list[dict]:
    seen_urls: set[str] = set()
    results: list[dict] = []

    for i, term in enumerate(search_terms):
        if i > 0:
            time.sleep(SCRAPE_DELAY_SECONDS)

        print(f"[scraper] Scraping: '{term}' in {SEARCH_LOCATION}")
        try:
            df = scrape_jobs(
                site_name=["linkedin"],
                search_term=term,
                location=SEARCH_LOCATION,
                results_wanted=RESULTS_PER_SEARCH,
                linkedin_fetch_description=True,
            )
            print(f"[scraper]   → {len(df)} results")
            for _, row in df.iterrows():
                url = _str(row.get("job_url"))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(_normalize_row(row))
        except Exception as e:
            print(f"[scraper] Error on '{term}': {e}")

    return results
