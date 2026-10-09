"""Lever agent (stage 8): Mobileye... - companies come from config/sources.json.

One request per company returns every open job with its full text:
GET https://<host>/v0/postings/<slug>?mode=json   (host: api.lever.co, or api.eu.lever.co for EU accounts)
"""

from datetime import datetime, timezone

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import fetch_json

API = "https://{host}/v0/postings/{slug}?mode=json"
DEFAULT_HOST = "api.lever.co"


def _description(raw: dict) -> str:
    """Intro + every list with its heading ("What will your job look like:", "All you need is:") + closing text."""
    parts = [html_to_text(raw.get("description")) or (raw.get("descriptionPlain") or "").strip()]
    for section in raw.get("lists") or []:
        parts.append(f"{(section.get('text') or '').strip()}\n{html_to_text(section.get('content'))}".strip())
    parts.append(html_to_text(raw.get("additional")) or (raw.get("additionalPlain") or "").strip())
    return "\n\n".join(p for p in parts if p)


def _posted_at(raw: dict) -> str | None:
    created = raw.get("createdAt")  # milliseconds since 1970
    if not created:
        return None
    return datetime.fromtimestamp(created / 1000, tz=timezone.utc).date().isoformat()


def to_job(raw: dict, company: dict) -> dict:
    """One Lever posting -> the job format of docs/agents/company-agents.md."""
    categories = raw.get("categories") or {}
    locations = categories.get("allLocations") or [categories.get("location") or ""]
    return {
        "id": f"lever:{company['slug']}:{raw['id']}",
        "source": f"lever:{company['slug']}",
        "company": company["company"],
        "title": (raw.get("text") or "").strip(),
        "url": raw.get("hostedUrl"),
        "apply_url": raw.get("applyUrl") or raw.get("hostedUrl"),
        "location": ", ".join(loc for loc in locations if loc),
        "job_number": None,  # Lever has no job number of its own; the id in the url is enough for duplicates
        "posted_at": _posted_at(raw),
        "description": _description(raw),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    raws = fetch_json(API.format(host=company.get("host", DEFAULT_HOST), slug=company["slug"]))
    jobs, in_israel = [], 0
    for raw in raws:
        job = to_job(raw, company)
        if not is_israel(job["location"], raw.get("country"), israel):
            continue
        in_israel += 1
        # Lever's "commitment" category ("Student", "Full time") counts for the keyword check, not as job text.
        commitment = (raw.get("categories") or {}).get("commitment") or ""
        keyword = matching_keyword(job["title"], f"{job['description']}\n{commitment}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(raws), "site_total": None, "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
