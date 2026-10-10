"""Eightfold agent (stage 8): Qualcomm, Teva... - companies come from config/sources.json.

Eightfold career sites answer on one of two API versions (the other gives 403), set per company as "api":
  pcsx      list: GET https://<host>/api/pcsx/search?domain=<d>&query=&location=Israel&start=n   -> data.positions
            text: GET https://<host>/api/pcsx/position_details?position_id=<id>&domain=<d>&hl=en
  apply_v2  list: GET https://<host>/api/apply/v2/jobs?domain=<d>&location=Israel&start=n&num=10  -> positions
            text: GET https://<host>/api/apply/v2/jobs/<id>?domain=<d>

Like Workday, the list has no job text: each text is fetched once and kept in <cache_dir>/<id>.json,
and deleted when the job leaves the site. The site's location filter is not exact (Teva lists a job in
Atlanta under Israel), so Israel is checked again in code.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_json
from jobhunter.state import _write_json

SITE_LOCATION = "Israel"


def _list_page(company: dict, start: int) -> tuple[list[dict], int]:
    host, domain = company["host"], company["domain"]
    if company["api"] == "pcsx":
        data = fetch_json(f"https://{host}/api/pcsx/search?domain={domain}&query=&location={SITE_LOCATION}&start={start}")["data"]
    else:
        data = fetch_json(f"https://{host}/api/apply/v2/jobs?domain={domain}&location={SITE_LOCATION}&start={start}&num=10")
    return data.get("positions") or [], data.get("count") or 0


def list_positions(company: dict) -> tuple[list[dict], int]:
    """Every position the site lists under Israel, page by page. Raises FetchError if the count doesn't add up."""
    positions: dict[str, dict] = {}
    page, site_total = _list_page(company, 0)
    while page:
        for position in page:
            positions.setdefault(str(position["id"]), position)
        if len(positions) >= site_total:
            break
        page, _ = _list_page(company, len(positions))
    if len(positions) != site_total:
        raise FetchError(f"listed {len(positions)} jobs but the site says {site_total}")
    return list(positions.values()), site_total


def _fetch_detail(company: dict, position_id: str) -> dict:
    """The job's details from the site, in one shape for both API versions."""
    host, domain = company["host"], company["domain"]
    if company["api"] == "pcsx":
        d = fetch_json(f"https://{host}/api/pcsx/position_details?position_id={position_id}&domain={domain}&hl=en")["data"]
        return {"title": d.get("name"), "other_title": None, "description_html": d.get("jobDescription"),
                "locations": d.get("locations") or [], "posted_ts": d.get("postedTs") or d.get("creationTs"),
                "url": d.get("publicUrl"), "job_number": d.get("displayJobId")}
    d = fetch_json(f"https://{host}/api/apply/v2/jobs/{position_id}?domain={domain}")
    return {"title": d.get("name"), "other_title": d.get("posting_name"), "description_html": d.get("job_description"),
            "locations": d.get("locations") or [d.get("location") or ""], "posted_ts": d.get("t_create"),
            "url": d.get("canonicalPositionUrl"), "job_number": d.get("display_job_id")}


def _detail(company: dict, position_id: str, cache_dir: Path | None) -> tuple[dict, bool]:
    """(details, fetched_now) - from the cache, or fetched once."""
    path = cache_dir / f"{position_id}.json" if cache_dir else None
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8")), False
    detail = _fetch_detail(company, position_id)
    if path:
        _write_json(path, detail)
    return detail, True


def to_job(position_id: str, detail: dict, company: dict) -> dict:
    """One Eightfold position -> the job format of docs/agents/company-agents.md."""
    posted = detail.get("posted_ts")
    url = detail.get("url") or f"https://{company['host']}/careers/job/{position_id}"
    return {
        "id": f"eightfold:{company['slug']}:{position_id}",
        "source": f"eightfold:{company['slug']}",
        "company": company["company"],
        "title": (detail.get("title") or "").strip(),
        "url": url,
        "apply_url": url,
        "location": ", ".join(loc for loc in detail.get("locations") or [] if loc),
        "job_number": detail.get("job_number"),
        "posted_at": datetime.fromtimestamp(posted, tz=timezone.utc).date().isoformat() if posted else None,
        "description": html_to_text(detail.get("description_html")),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    positions, site_total = list_positions(company)
    jobs, in_israel, fetched = [], 0, 0
    for position in positions:
        position_id = str(position["id"])
        detail, fetched_now = _detail(company, position_id, cache_dir)
        fetched += fetched_now
        job = to_job(position_id, detail, company)
        if not is_israel(job["location"], None, israel):
            continue
        in_israel += 1
        # Teva gives a Hebrew title and an English posting name; both count for the keyword check.
        title_text = f"{job['title']} {detail.get('other_title') or ''}"
        keyword = matching_keyword(title_text, job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    if cache_dir and cache_dir.exists():  # forget the texts of jobs that left the site
        listed = {f"{p['id']}.json" for p in positions}
        for path in cache_dir.glob("*.json"):
            if path.name not in listed:
                path.unlink()
    stats = {"total": len(positions), "site_total": site_total, "israel": in_israel,
             "matched": len(jobs), "texts_fetched": fetched}
    return jobs, stats
