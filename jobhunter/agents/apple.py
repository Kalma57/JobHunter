"""Apple agent (stage 8, tier 2): jobs.apple.com.

Apple's pages carry their data inside the HTML (window.__staticRouterHydrationData), and the search page has
no page-by-page address, so instead of listing every job the agent uses Apple's own search, once per keyword:
    https://jobs.apple.com/en-us/search?search=<keyword>&location=israel-ISR   (a handful of results each)
Apple's search is fuzzy, so every result is checked again in code (whole words, title + full text).
Full text: https://jobs.apple.com/en-us/details/<id>/<slug>, fetched once per job and kept (cache.py).
The Israel total for the run report comes from the same search page without a keyword.
"""

import json
import re
from pathlib import Path
from urllib.parse import quote

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError, fetch_text

SITE = "https://jobs.apple.com/en-us"
SEARCH = SITE + "/search?search={keyword}&location={location}"
DETAILS = SITE + "/details/{id}/{slug}"
HYDRATION = re.compile(r'window\.__staticRouterHydrationData = JSON\.parse\("(.*?)"\);', re.S)


def page_data(html: str) -> dict:
    """The JSON Apple embeds in its pages (a JSON string inside JSON.parse("...")) -> loaderData."""
    m = HYDRATION.search(html)
    if not m:
        raise FetchError("Apple page without its embedded data - the site may have changed")
    return json.loads(json.loads(f'"{m.group(1)}"'))["loaderData"]


def search(company: dict, keyword: str) -> tuple[list[dict], int]:
    data = page_data(fetch_text(SEARCH.format(keyword=quote(keyword), location=company.get("location", "israel-ISR"))))["search"]
    return data.get("searchResults") or [], data.get("totalRecords") or 0


def _fetch_detail(result: dict) -> dict:
    d = page_data(fetch_text(DETAILS.format(id=result["id"], slug=result["transformedPostingTitle"])))["jobDetails"]["jobsData"]
    return {
        "title": d.get("postingTitle"),
        "sections": [{"title": t, "text": d.get(k)} for t, k in (("Summary", "jobSummary"), ("Description", "description"),
                                                                 ("Minimum qualifications", "minimumQualifications"),
                                                                 ("Preferred qualifications", "preferredQualifications"))],
        "teams": d.get("teamNames") or [],
        "job_number": d.get("jobNumber") or result.get("reqId"),
    }


def _location(result: dict) -> str:
    names = []
    for loc in result.get("locations") or []:
        names += [loc.get("name") or "", loc.get("countryName") or ""]
    return ", ".join(dict.fromkeys(n for n in names if n))


def to_job(result: dict, detail: dict, company: dict) -> dict:
    """One Apple search result + its details -> the job format of docs/agents/company-agents.md."""
    parts = []
    for section in detail.get("sections") or []:
        text = html_to_text(section.get("text"))
        if text:
            parts.append(f"{section['title']}\n{text}")
    url = DETAILS.format(id=result["id"], slug=result["transformedPostingTitle"])
    return {
        "id": f"apple:{result['id']}",
        "source": f"apple:{company['slug']}",
        "company": company["company"],
        "title": (result.get("postingTitle") or detail.get("title") or "").strip(),
        "url": url,
        "apply_url": url,
        "location": _location(result),
        "job_number": detail.get("job_number"),
        "posted_at": (result.get("postDateInGMT") or "")[:10] or None,
        "description": "\n\n".join(parts),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword, and counts for the run report. Raises FetchError if the site can't be read."""
    _, israel_total = search(company, "")
    results: dict[str, dict] = {}
    for keyword in keywords:
        for result in search(company, keyword)[0]:
            results.setdefault(result["id"], result)
    texts = TextCache(cache_dir)
    jobs = []
    for result in results.values():
        detail = texts.get(re.sub(r"[^A-Za-z0-9.-]", "-", result["id"]), lambda: _fetch_detail(result))
        job = to_job(result, detail, company)
        if not is_israel(job["location"], None, israel):
            continue
        # Apple's team names ("Students") count for the keyword check, not as job text
        keyword = matching_keyword(job["title"], f"{job['description']}\n{' '.join(detail.get('teams') or [])}", keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    # The cache is not pruned here: the agent only sees search results, not the full list of open jobs.
    stats = {"total": israel_total, "site_total": israel_total, "israel": israel_total,
             "searched": len(results), "matched": len(jobs), "texts_fetched": texts.fetched}
    return jobs, stats
