"""SmartRecruiters agent (stage 8, tier 2): Wix... - companies come from config/sources.json.

List (filtered to Israel by the site): GET https://api.smartrecruiters.com/v1/companies/<id>/postings?country=il&limit=100&offset=n
Text:                                  GET https://api.smartrecruiters.com/v1/companies/<id>/postings/<posting id>
The list has no job text, so each text is fetched once and kept (cache.py).
SmartRecruiters answers 200 with an empty list even for a company that doesn't exist - a company that suddenly
lists 0 jobs shows up as the runner's zero-drop warning.
"""

from pathlib import Path

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_json

API = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
PAGE_SIZE = 100


def list_postings(company: dict) -> tuple[list[dict], int]:
    postings: dict[str, dict] = {}
    offset, site_total = 0, None
    while site_total is None or offset < site_total:
        data = fetch_json(f"{API.format(company_id=company['company_id'])}?country=il&limit={PAGE_SIZE}&offset={offset}")
        site_total = data.get("totalFound") or 0
        page = data.get("content") or []
        for posting in page:
            postings.setdefault(str(posting["id"]), posting)
        if not page:
            break
        offset += PAGE_SIZE
    if len(postings) != site_total:
        raise FetchError(f"listed {len(postings)} jobs but the site says {site_total}")
    return list(postings.values()), site_total


def _fetch_detail(company: dict, posting_id: str) -> dict:
    d = fetch_json(f"{API.format(company_id=company['company_id'])}/{posting_id}")
    sections = (d.get("jobAd") or {}).get("sections") or {}
    return {
        "title": d.get("name"),
        "sections": [{"title": (sections.get(k) or {}).get("title"), "html": (sections.get(k) or {}).get("text")}
                     for k in ("jobDescription", "qualifications", "additionalInformation", "companyDescription")],
        "location": (d.get("location") or {}).get("fullLocation") or (d.get("location") or {}).get("city"),
        "country": (d.get("location") or {}).get("country"),
        "posted": d.get("releasedDate"),
        "url": d.get("postingUrl"),
        "apply_url": d.get("applyUrl"),
        "ref_number": d.get("refNumber"),
        "tags": " ".join(x for x in ((d.get("experienceLevel") or {}).get("label"), (d.get("typeOfEmployment") or {}).get("label")) if x),
    }


def to_job(posting_id: str, detail: dict, company: dict) -> dict:
    """One SmartRecruiters posting -> the job format of docs/agents/company-agents.md."""
    parts = []
    for section in detail.get("sections") or []:
        text = html_to_text(section.get("html"))
        if text:
            parts.append(f"{section.get('title') or ''}\n{text}".strip())
    return {
        "id": f"smartrecruiters:{company['slug']}:{posting_id}",
        "source": f"smartrecruiters:{company['slug']}",
        "company": company["company"],
        "title": (detail.get("title") or "").strip(),
        "url": detail.get("url"),
        "apply_url": detail.get("apply_url") or detail.get("url"),
        "location": (detail.get("location") or "").replace(", ,", ","),
        "job_number": None,
        "posted_at": (detail.get("posted") or "")[:10] or None,
        "description": "\n\n".join(parts),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    postings, site_total = list_postings(company)
    texts = TextCache(cache_dir)
    jobs, in_israel = [], 0
    for posting in postings:
        posting_id = str(posting["id"])
        detail = texts.get(posting_id, lambda: _fetch_detail(company, posting_id))
        job = to_job(posting_id, detail, company)
        if not is_israel(job["location"], detail.get("country"), israel):
            continue
        in_israel += 1
        # SmartRecruiters' experience level / employment type ("Internship", "Entry Level") count for keywords only
        keyword = matching_keyword(job["title"], f"{job['description']}\n{detail.get('tags') or ''}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    texts.keep_only({str(p["id"]) for p in postings})
    stats = {"total": len(postings), "site_total": site_total, "israel": in_israel,
             "matched": len(jobs), "texts_fetched": texts.fetched}
    return jobs, stats
