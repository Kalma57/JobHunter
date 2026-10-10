"""Google agent (stage 8, tier 2): google.com/about/careers (Google, DeepMind and the other Alphabet companies listed there).

The results page carries its data inside the HTML (AF_initDataCallback, key 'ds:1'), full job texts included:
    https://www.google.com/about/careers/applications/jobs/results?location=Israel&q=<keyword>&page=<n>
ds:1 = [jobs, None, total, page_size]. Like Apple, the agent uses the site's own search once per keyword
(Google's search is fuzzy, so every result is checked again in code) - no per-job requests are needed.
The Israel total for the run report comes from the same page without a keyword.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_text

RESULTS = "https://www.google.com/about/careers/applications/jobs/results"
SEARCH = RESULTS + "?location={location}&q={keyword}&page={page}"
DATA = re.compile(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", re.S)
MAX_PAGES = 10


def page_data(html: str) -> list:
    m = DATA.search(html)
    if not m:
        raise FetchError("Google results page without its embedded data - the site may have changed")
    return json.loads(m.group(1))


def search(company: dict, keyword: str) -> tuple[list[list], int]:
    """Every result of one search, page by page (20 per page)."""
    results: dict[str, list] = {}
    total = 0
    for page in range(1, MAX_PAGES + 1):
        data = page_data(fetch_text(SEARCH.format(location=quote(company.get("location", "Israel")), keyword=quote(keyword), page=page)))
        jobs, total = data[0] or [], data[2] or 0
        for raw in jobs:
            results.setdefault(raw[0], raw)
        if not jobs or len(results) >= total:
            break
    return list(results.values()), total


def _text(field) -> str:
    return html_to_text(field[1]) if isinstance(field, list) and len(field) > 1 and field[1] else ""


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def to_job(raw: list, company: dict) -> dict:
    """One Google result row -> the job format of docs/agents/company-agents.md."""
    job_id, title = raw[0], (raw[1] or "").strip()
    sections = [("About the job", raw[10]), ("Responsibilities", raw[3]), ("Qualifications", raw[4]),
                ("More", raw[15]), ("Locations", raw[18])]
    parts = [f"{name}\n{text}" for name, field in sections if (text := _text(field))]
    locations = raw[9] or []
    created = raw[12][0] if isinstance(raw[12], list) and raw[12] else None
    employer = raw[7] or company["company"]
    return {
        "id": f"google:{job_id}",
        "source": f"google:{company['slug']}",
        "company": employer if employer == company["company"] else f"{company['company']} ({employer})",
        "title": title,
        "url": f"{RESULTS}/{job_id}-{_slug(title)}",
        "apply_url": raw[2] or f"{RESULTS}/{job_id}-{_slug(title)}",
        "location": ", ".join(loc[0] for loc in locations if loc and loc[0]),
        "job_number": job_id,
        "posted_at": datetime.fromtimestamp(created, tz=timezone.utc).date().isoformat() if created else None,
        "description": "\n\n".join(parts),
        "_countries": [loc[5] for loc in locations if loc and len(loc) > 5 and loc[5]],
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    israel_total = page_data(fetch_text(SEARCH.format(location=quote(company.get("location", "Israel")), keyword="", page=1)))[2] or 0
    results: dict[str, list] = {}
    for keyword in keywords:
        for raw in search(company, keyword)[0]:
            results.setdefault(raw[0], raw)
    jobs = []
    for raw in results.values():
        job = to_job(raw, company)
        countries = job.pop("_countries")
        if not is_israel(job["location"], "IL" if "IL" in countries else None, israel):
            continue
        keyword = matching_keyword(job["title"], job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": israel_total, "site_total": israel_total, "israel": israel_total,
             "searched": len(results), "matched": len(jobs)}
    return jobs, stats
