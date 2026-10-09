"""Greenhouse agent (stage 8): Nebius, ScaleOps, Cato Networks... - companies come from config/sources.json.

One request per company returns every open job with its full text:
GET https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true
"""

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import fetch_json

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def _locations(raw: dict) -> str:
    """The job's own location field only. Not `offices`: it lists every office the job is attached to,
    so the Amsterdam / London copies of a job (Nebius posts one copy per city) would count as Israel too."""
    name = (raw.get("location") or {}).get("name") or ""
    return ", ".join(part.strip() for part in name.split(";") if part.strip())


def to_job(raw: dict, company: dict) -> dict:
    """One Greenhouse posting -> the job format of docs/agents/company-agents.md."""
    return {
        "id": f"greenhouse:{company['slug']}:{raw['id']}",
        "source": f"greenhouse:{company['slug']}",
        "company": company["company"],
        "title": (raw.get("title") or "").strip(),
        "url": raw.get("absolute_url"),
        "apply_url": raw.get("absolute_url"),  # the application form is on the same page
        "location": _locations(raw),
        "job_number": raw.get("requisition_id"),
        "posted_at": (raw.get("first_published") or raw.get("updated_at") or "")[:10] or None,
        "description": html_to_text(raw.get("content")),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    data = fetch_json(API.format(slug=company["slug"]))
    raws = data.get("jobs", [])
    jobs, in_israel = [], 0
    for raw in raws:
        job = to_job(raw, company)
        if not is_israel(job["location"], None, israel):
            continue
        in_israel += 1
        keyword = matching_keyword(job["title"], job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(raws), "site_total": (data.get("meta") or {}).get("total"),
             "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
