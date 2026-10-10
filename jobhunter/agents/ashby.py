"""Ashby agent (stage 8, tier 2): monday.com... - companies come from config/sources.json.

One request per company returns every listed job with its full text:
GET https://api.ashbyhq.com/posting-api/job-board/<board>
"""

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import fetch_json

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


def _locations(raw: dict) -> str:
    country = ((raw.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
    places = [raw.get("location") or ""] + [s.get("location") or "" for s in raw.get("secondaryLocations") or [] if isinstance(s, dict)]
    if country:
        places.append(country)
    return ", ".join(dict.fromkeys(p for p in places if p))


def to_job(raw: dict, company: dict) -> dict:
    """One Ashby posting -> the job format of docs/agents/company-agents.md."""
    return {
        "id": f"ashby:{company['slug']}:{raw['id']}",
        "source": f"ashby:{company['slug']}",
        "company": company["company"],
        "title": (raw.get("title") or "").strip(),
        "url": raw.get("jobUrl"),
        "apply_url": raw.get("applyUrl") or raw.get("jobUrl"),
        "location": _locations(raw),
        "job_number": None,
        "posted_at": (raw.get("publishedAt") or "")[:10] or None,
        "description": html_to_text(raw.get("descriptionHtml")) or (raw.get("descriptionPlain") or "").strip(),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    raws = [r for r in fetch_json(API.format(board=company["board"])).get("jobs") or [] if r.get("isListed", True)]
    jobs, in_israel = [], 0
    for raw in raws:
        job = to_job(raw, company)
        if not is_israel(job["location"], None, israel):
            continue
        in_israel += 1
        # Ashby's employment type ("Intern") counts for the keyword check, not as job text
        keyword = matching_keyword(job["title"], f"{job['description']}\n{raw.get('employmentType') or ''}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(raws), "site_total": None, "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
