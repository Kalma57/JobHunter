"""Comeet agent (stage 8): DriveNets, Nova... - companies come from config/sources.json.

One request per company returns every open job with its full text:
GET https://www.comeet.co/careers-api/2.0/company/<uid>/positions?token=<token>&details=true

<uid> and <token> are the public ones the company's own careers widget uses; both appear on its public
Comeet page (https://www.comeet.com/jobs/<comeet-slug>/<uid>, in COMPANY_DATA). If a company rotates its
token the request fails, the run report shows the error, and the token in the config is updated.
"""

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import fetch_json

API = "https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}&details=true"


def _description(raw: dict) -> str:
    """Every details section with its heading ("Description", "Requirements"...)."""
    parts = []
    for section in raw.get("details") or []:
        text = html_to_text(section.get("value"))
        if text:
            parts.append(f"{(section.get('name') or '').strip()}\n{text}".strip())
    return "\n\n".join(parts)


def to_job(raw: dict, company: dict) -> dict:
    """One Comeet position -> the job format of docs/agents/company-agents.md."""
    location = raw.get("location") or {}
    hosted = raw.get("url_comeet_hosted_page") or raw.get("url_recruit_hosted_page")
    return {
        "id": f"comeet:{company['slug']}:{raw['uid']}",
        "source": f"comeet:{company['slug']}",
        "company": company["company"],
        "title": (raw.get("name") or "").strip(),
        "url": raw.get("url_active_page") or hosted,  # the job on the company's own site when it has one
        "apply_url": hosted,  # the Comeet page carries the application form
        "location": ", ".join(p for p in (location.get("name"), location.get("city")) if p),
        "job_number": raw.get("uid"),
        "posted_at": (raw.get("time_updated") or "")[:10] or None,  # Comeet gives the last update, not the first post
        "description": _description(raw),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    raws = fetch_json(API.format(uid=company["uid"], token=company["token"]))
    jobs, in_israel = [], 0
    for raw in raws:
        job = to_job(raw, company)
        if not is_israel(job["location"], (raw.get("location") or {}).get("country"), israel):
            continue
        in_israel += 1
        # Comeet's employment type / experience level ("Entry-level", "Student") count for the keyword check, not as text.
        tags = " ".join(t for t in (raw.get("employment_type"), raw.get("experience_level")) if t)
        keyword = matching_keyword(job["title"], f"{job['description']}\n{tags}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(raws), "site_total": None, "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
