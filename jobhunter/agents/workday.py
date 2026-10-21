"""Workday agent (stage 8): NVIDIA, KLA, Applied Materials... - companies come from config/sources.json.

The job list has no job text, and each job's text is one more request, so texts are fetched once per job
and kept (cache.py).

List:   POST https://<host>/wday/cxs/<tenant>/<site>/jobs   {"appliedFacets": {<israel facet>}, "limit": 20, "offset": n}
Detail: GET  https://<host>/wday/cxs/<tenant>/<site><externalPath>

Workday's own searchText is fuzzy ("intern" finds "international"), so keywords are checked in code on the full text.
"""

import re
from pathlib import Path

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_json

PAGE_SIZE = 20  # Workday's maximum


def _base(company: dict) -> str:
    return f"https://{company['host']}/wday/cxs/{company['tenant']}/{company['site']}"


def _list_page(company: dict, facets: dict, offset: int) -> dict:
    return fetch_json(f"{_base(company)}/jobs", {"appliedFacets": facets, "limit": PAGE_SIZE, "offset": offset, "searchText": ""})


def israel_facet(facets: list[dict]) -> dict:
    """The site's own location filter option named exactly "Israel" (Country on KLA, locationHierarchy1 on NVIDIA...).

    Facets can be nested one level (locationMainGroup -> locationHierarchy1 -> values).
    """
    def walk(facet_list):
        for facet in facet_list:
            for value in facet.get("values") or []:
                if "values" in value:  # a nested facet
                    yield from walk([value])
                elif (value.get("descriptor") or "").strip().lower() == "israel":
                    yield facet["facetParameter"], value["id"]

    found = list(walk(facets))
    if found:
        parameter, value_id = found[0]
        return {parameter: [value_id]}
    # No single "Israel" option (Palo Alto lists offices: "Office - Israel - Tel Aviv", "Remote - Israel"...):
    # take every option of one location filter that names Israel - the site ORs options of the same filter.
    def walk_named(facet_list):
        for facet in facet_list:
            for value in facet.get("values") or []:
                if "values" in value:
                    yield from walk_named([value])
                elif re.search(r"\bIsrael\b", value.get("descriptor") or "", re.I):
                    yield facet["facetParameter"], value["id"]

    by_parameter: dict[str, list[str]] = {}
    for parameter, value_id in walk_named(facets):
        by_parameter.setdefault(parameter, []).append(value_id)
    if not by_parameter:
        raise FetchError("no 'Israel' option in the site's location filters")
    parameter = max(by_parameter, key=lambda p: len(by_parameter[p]))
    return {parameter: by_parameter[parameter]}


def list_israel(company: dict) -> tuple[list[dict], int]:
    """Every posting in the Israel filter, page by page to the end. Raises FetchError if the count doesn't add up."""
    first = _list_page(company, {}, 0)
    facets = israel_facet(first.get("facets") or [])
    page = _list_page(company, facets, 0)
    site_total = page.get("total") or 0  # Workday sends the total on the first page only
    postings: dict[str, dict] = {}
    broken = 0  # an entry without its job link (NVIDIA, 21/10/2026: one odd entry made the whole company fail)
    offset = 0
    while True:
        for posting in page.get("jobPostings") or []:
            if not posting.get("externalPath"):
                broken += 1
                continue
            postings.setdefault(posting["externalPath"], posting)
        offset += PAGE_SIZE
        if not page.get("jobPostings") or offset >= site_total:
            break
        page = _list_page(company, facets, offset)
    if len(postings) + broken != site_total:
        raise FetchError(f"listed {len(postings)} jobs in Israel but the site says {site_total}")
    return list(postings.values()), site_total


def job_key(external_path: str) -> str:
    """The job number at the end of the path: /job/Israel-Yokneam/Senior-..._JR2026683 -> JR2026683."""
    tail = external_path.rsplit("_", 1)[-1] if "_" in external_path else external_path.rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9.-]", "-", tail)


def _fetch_detail(company: dict, posting: dict) -> dict:
    info = fetch_json(f"{_base(company)}{posting['externalPath']}").get("jobPostingInfo") or {}
    return {k: info.get(k) for k in ("title", "jobDescription", "location", "additionalLocations",
                                     "startDate", "jobReqId", "externalUrl", "country")}


def to_job(posting: dict, detail: dict, company: dict) -> dict:
    """One Workday posting + its details -> the job format of docs/agents/company-agents.md."""
    locations = [detail.get("location") or posting.get("locationsText") or ""] + list(detail.get("additionalLocations") or [])
    url = detail.get("externalUrl") or f"https://{company['host']}/{company['site']}{posting['externalPath']}"
    return {
        "id": f"workday:{company['slug']}:{job_key(posting['externalPath'])}",
        "source": f"workday:{company['slug']}",
        "company": company["company"],
        "title": (detail.get("title") or posting.get("title") or "").strip(),
        "url": url,
        "apply_url": url,
        "location": ", ".join(loc for loc in locations if loc),
        "job_number": detail.get("jobReqId"),
        "posted_at": detail.get("startDate"),
        "description": html_to_text(detail.get("jobDescription")),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    postings, site_total = list_israel(company)
    texts = TextCache(cache_dir)
    jobs, in_israel = [], 0
    for posting in postings:
        detail = texts.get(job_key(posting["externalPath"]), lambda: _fetch_detail(company, posting))
        job = to_job(posting, detail, company)
        country = "IL" if ((detail.get("country") or {}).get("descriptor") or "").lower() == "israel" else None
        if not is_israel(job["location"], country, israel):
            continue
        in_israel += 1
        keyword = matching_keyword(job["title"], job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    texts.keep_only({job_key(p["externalPath"]) for p in postings})  # forget the texts of jobs that left the site
    stats = {"total": len(postings), "site_total": site_total, "israel": in_israel,
             "matched": len(jobs), "texts_fetched": texts.fetched}
    return jobs, stats
