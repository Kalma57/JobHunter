"""Oracle Recruiting Cloud agent (stage 8, tier 2): Oracle itself... - companies come from config/sources.json.

List (filtered by the site's location search): GET https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions
    ?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=<site>,keyword=,location=Israel,limit=25,offset=n
Text: GET https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
    ?expand=all&onlyData=true&finder=ById;Id="<id>",siteNumber=<site>
The list has no full text, so each text is fetched once and kept (cache.py).
"""

from pathlib import Path
from urllib.parse import quote

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_json

PAGE_SIZE = 25
SITE_LOCATION = "Israel"


def _base(company: dict) -> str:
    return f"https://{company['host']}/hcmRestApi/resources/latest"


def list_requisitions(company: dict) -> tuple[list[dict], int]:
    found: dict[str, dict] = {}
    offset, site_total = 0, None
    while site_total is None or offset < site_total:
        finder = f"findReqs;siteNumber={company['site']},keyword=,location={SITE_LOCATION},limit={PAGE_SIZE},offset={offset}"
        data = fetch_json(f"{_base(company)}/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder={quote(finder, safe=';,=')}")
        item = (data.get("items") or [{}])[0]
        site_total = item.get("TotalJobsCount") or 0
        page = item.get("requisitionList") or []
        for req in page:
            found.setdefault(str(req["Id"]), req)
        if not page:
            break
        offset += PAGE_SIZE
    if len(found) != site_total:
        raise FetchError(f"listed {len(found)} jobs but the site says {site_total}")
    return list(found.values()), site_total


def _fetch_detail(company: dict, req_id: str) -> dict:
    finder = f'ById;Id="{req_id}",siteNumber={company["site"]}'
    data = fetch_json(f"{_base(company)}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder={quote(finder, safe=';,=')}")
    d = (data.get("items") or [{}])[0]
    return {
        "title": d.get("Title"),
        "sections": [{"title": t, "html": d.get(k)} for t, k in (("Description", "ExternalDescriptionStr"),
                                                                 ("Responsibilities", "ExternalResponsibilitiesStr"),
                                                                 ("Qualifications", "ExternalQualificationsStr"))],
        "location": d.get("PrimaryLocation"),
        "country": d.get("PrimaryLocationCountry"),
        "posted": d.get("ExternalPostedStartDate"),
        "tags": " ".join(x for x in (d.get("JobLevel"), d.get("JobSchedule"), d.get("RequisitionType")) if isinstance(x, str)),
    }


def to_job(req_id: str, detail: dict, company: dict) -> dict:
    """One Oracle requisition -> the job format of docs/agents/company-agents.md."""
    parts = []
    for section in detail.get("sections") or []:
        text = html_to_text(section.get("html"))
        if text:
            parts.append(f"{section['title']}\n{text}")
    url = company["job_url"].format(id=req_id)  # the company's public careers page for the job
    return {
        "id": f"oracle:{company['slug']}:{req_id}",
        "source": f"oracle:{company['slug']}",
        "company": company["company"],
        "title": (detail.get("title") or "").strip(),
        "url": url,
        "apply_url": url,
        "location": detail.get("location") or "",
        "job_number": req_id,
        "posted_at": (detail.get("posted") or "")[:10] or None,
        "description": "\n\n".join(parts),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    reqs, site_total = list_requisitions(company)
    texts = TextCache(cache_dir)
    jobs, in_israel = [], 0
    for req in reqs:
        req_id = str(req["Id"])
        detail = texts.get(req_id, lambda: _fetch_detail(company, req_id))
        job = to_job(req_id, detail, company)
        if not is_israel(job["location"], detail.get("country"), israel):
            continue
        in_israel += 1
        keyword = matching_keyword(job["title"], f"{job['description']}\n{detail.get('tags') or ''}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    texts.keep_only({str(r["Id"]) for r in reqs})
    stats = {"total": len(reqs), "site_total": site_total, "israel": in_israel,
             "matched": len(jobs), "texts_fetched": texts.fetched}
    return jobs, stats
