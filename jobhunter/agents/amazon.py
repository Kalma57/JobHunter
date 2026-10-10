"""Amazon agent (stage 8, tier 2): amazon.jobs - Amazon and Annapurna Labs share it.

The site's own search API returns full job texts, 100 per page, filtered to Israel by the site:
GET https://www.amazon.jobs/en/search.json?country=ISR&result_limit=100&offset=<n>&base_query=
"""

from datetime import datetime

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_json

API = "https://www.amazon.jobs/en/search.json?country={country}&result_limit={limit}&offset={offset}&base_query="
PAGE_SIZE = 100
SITE = "https://www.amazon.jobs"


def list_jobs(company: dict) -> tuple[list[dict], int]:
    """Every job the site lists for the country, page by page. Raises FetchError if the count doesn't add up."""
    jobs: dict[str, dict] = {}
    offset, site_total = 0, None
    while site_total is None or offset < site_total:
        data = fetch_json(API.format(country=company.get("country", "ISR"), limit=PAGE_SIZE, offset=offset))
        site_total = data.get("hits") or 0
        page = data.get("jobs") or []
        for raw in page:
            jobs.setdefault(str(raw["id_icims"]), raw)
        if not page:
            break
        offset += PAGE_SIZE
    if len(jobs) != site_total:
        raise FetchError(f"listed {len(jobs)} jobs but the site says {site_total}")
    return list(jobs.values()), site_total


def _description(raw: dict) -> str:
    parts = [html_to_text(raw.get("description"))]
    for heading, field in (("Basic qualifications", "basic_qualifications"), ("Preferred qualifications", "preferred_qualifications")):
        text = html_to_text(raw.get(field))
        if text:
            parts.append(f"{heading}\n{text}")
    return "\n\n".join(p for p in parts if p)


def _posted_at(raw: dict) -> str | None:
    try:
        return datetime.strptime((raw.get("posted_date") or "").strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def to_job(raw: dict, company: dict) -> dict:
    """One amazon.jobs posting -> the job format of docs/agents/company-agents.md."""
    employer = (raw.get("company_name") or "").strip()
    return {
        "id": f"amazon:{raw['id_icims']}",
        "source": f"amazon:{company['slug']}",
        # Annapurna Labs is Amazon's; keep the legal employer visible ("Amazon (Annapurna Labs Ltd.)")
        "company": company["company"] if not employer or employer.lower().startswith("amazon") else f"{company['company']} ({employer})",
        "title": (raw.get("title") or "").strip(),
        "url": f"{SITE}{raw.get('job_path') or ''}",
        "apply_url": raw.get("url_next_step") or f"{SITE}{raw.get('job_path') or ''}",
        "location": raw.get("normalized_location") or raw.get("location") or "",
        "job_number": str(raw["id_icims"]),
        "posted_at": _posted_at(raw),
        "description": _description(raw),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    raws, site_total = list_jobs(company)
    jobs, in_israel = [], 0
    for raw in raws:
        job = to_job(raw, company)
        country = "IL" if (raw.get("country_code") or "").upper() in ("IL", "ISR") else None
        if not is_israel(job["location"], country, israel):
            continue
        in_israel += 1
        # amazon.jobs marks internships itself (is_intern); it counts for the keyword check, not as job text
        tags = "Intern" if raw.get("is_intern") else ""
        keyword = matching_keyword(job["title"], f"{job['description']}\n{tags}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(raws), "site_total": site_total, "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
