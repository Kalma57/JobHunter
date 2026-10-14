"""Drushim agent (stage 9): the Israeli job board www.drushim.co.il.

The site's own pages read their search results from its public web API (webapi.drushim.co.il), and robots.txt
allows it (it only asks tools not to call the search with "area=" and the job API with "jobcode="). One request
returns 10 jobs with their full text (description + requirements), so no job page is opened.

Search = data (config/sources.json, "queries"): a search word in a category, e.g. "סטודנט" in hi-tech (catdir 5)
and engineering (catdir 10) - without the category the word "סטודנט" brings 950+ jobs, mostly guards and sales.
Every page of every query is read, until a page comes back empty or says there is no next page (NextPageNumber -1;
max_pages caps a broken paging). English words return nothing on this site, so the queries are Hebrew. Keywords are checked again in code.

The company is the employer as the board shows it; a hidden one ("- חסוי -") becomes "חסוי — דרך דרושים".
"""

import re
from html import unescape
from urllib.parse import quote

from jobhunter.agents.filters import matching_keyword
from jobhunter.agents.http import fetch_json

API = "https://webapi.drushim.co.il/api/jobs/search?searchterm={term}&catdir={catdir}&page={page}"
SITE = "https://www.drushim.co.il"
HIDDEN_COMPANY = "חסוי — דרך דרושים"
MAX_PAGES = 15


def _text(html: str | None) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def to_job(raw: dict, company: dict) -> dict:
    content, info = raw.get("JobContent") or {}, raw.get("JobInfo") or {}
    employer = ((raw.get("Company") or {}).get("CompanyDisplayName") or "").strip()
    if not employer or "חסוי" in employer:
        employer = HIDDEN_COMPANY
    cities = [a.get("City") for a in content.get("Addresses") or [] if a.get("City")]
    regions = [r.get("NameInHebrew") for r in content.get("Regions") or [] if r.get("NameInHebrew")]
    description = _text(content.get("Description"))
    requirements = _text(content.get("Requirements"))
    scopes = ", ".join(s.get("NameInHebrew", "") for s in content.get("Scopes") or [])
    experience = (content.get("Experience") or {}).get("NameInHebrew")
    parts = [description]
    if requirements:
        parts.append("דרישות:\n" + requirements)
    details = [f"היקף: {scopes}" if scopes else "", f"ניסיון (לפי האתר): {experience}" if experience else ""]
    parts.append("\n".join(d for d in details if d))
    url = SITE + info["Link"] if info.get("Link") else None
    return {
        "id": f"drushim:{info.get('JobCode') or raw.get('Code')}",
        "source": f"drushim:{company['slug']}",
        "company": employer,
        "title": (content.get("Name") or "").strip(),
        "url": url,
        "apply_url": url,
        "location": ", ".join(dict.fromkeys(cities or regions)),
        "job_number": info.get("EmployerJobCode") or None,
        "posted_at": (info.get("Date") or "")[:10] or None,
        "description": "\n\n".join(p for p in parts if p),
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs of every query that match a keyword (the whole site is Israel), and counts for the run report."""
    by_id: dict[str, dict] = {}
    listed = 0
    site_total = 0
    for query in company["queries"]:
        for page in range(1, company.get("max_pages", MAX_PAGES) + 1):
            data = fetch_json(API.format(term=quote(query["term"]), catdir=query["catdir"], page=page))
            if page == 1:
                site_total += data.get("TotalSearchResultCount") or 0
            results = data.get("ResultList") or []
            for raw in results:
                listed += 1
                job = to_job(raw, company)
                keyword = matching_keyword(job["title"], job["description"], keywords)
                if keyword and job["id"] not in by_id:
                    job["matched_keyword"] = keyword
                    by_id[job["id"]] = job
            if not results or (data.get("NextPageNumber") or -1) < 0:
                break
    jobs = list(by_id.values())
    return jobs, {"total": listed, "site_total": site_total, "israel": listed, "matched": len(jobs)}
