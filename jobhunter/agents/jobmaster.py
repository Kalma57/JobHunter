"""JobMaster agent (stage 9): the Israeli job board www.jobmaster.co.il.

robots.txt allows the search pages and the job pages (it only asks tools not to call /api/). The search page
is plain HTML: 10 job cards, newest first (<article id="misra<number>">: title, company, city, short text).
The next pages (?currPage=2...) show a sign-in page to visitors - a wall, so only the first page of each search
is read (the 10 newest; read every morning, that is what's new). The full text is on the job page (checknum.asp?key=<number>), read once per job
and kept (cache.py) - only for cards whose title or short text matches a keyword.

Search = data (config/sources.json, "queries"): search paths such as "q-סטודנט-תוכנה".
"""

import re
from html import unescape
from pathlib import Path
from urllib.parse import quote

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import matching_keyword
from jobhunter.agents.http import fetch_text

SITE = "https://www.jobmaster.co.il"
SEARCH = SITE + "/jobs/{query}/"
JOB = SITE + "/jobs/checknum.asp?key={key}"
HIDDEN_COMPANY = "חסוי — דרך JobMaster"

CARD = re.compile(r'<article id="misra(?P<key>\d+)"(?P<body>.*?)</article>', re.S)
TITLE = re.compile(r'class="CardHeader[^"]*"[^>]*>(?P<v>.*?)</a>', re.S)
COMPANY = re.compile(r'class="[^"]*CompanyNameLink[^"]*"[^>]*>\s*<span>(?P<v>.*?)</span>', re.S)
CITY = re.compile(r'<li class="jobLocation">(?P<v>.*?)</li>', re.S)
SHORT = re.compile(r'class="jobShortDescription[^"]*"[^>]*>(?P<v>.*?)</div>', re.S)
FULL = {"description": re.compile(r'id="jobDescriptionContent"[^>]*>(?P<v>.*?)</div>', re.S),
        "requirements": re.compile(r'id="jobRequirementsContent"[^>]*>(?P<v>.*?)</div>', re.S)}


def _text(html: str | None) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip())


def _one(pattern: re.Pattern, html: str) -> str:
    m = pattern.search(html)
    return _text(m.group("v")) if m else ""


def parse_cards(html: str) -> list[dict]:
    return [{"key": m.group("key"), "title": _one(TITLE, m.group("body")), "company": _one(COMPANY, m.group("body")),
             "city": " ".join(_one(CITY, m.group("body")).split()), "short": _one(SHORT, m.group("body"))}
            for m in CARD.finditer(html)]


def parse_job_page(html: str) -> dict:
    return {field: _one(pattern, html) for field, pattern in FULL.items()}


def to_job(card: dict, full: dict, company: dict) -> dict:
    url = JOB.format(key=card["key"])
    parts = [full.get("description") or card["short"]]
    if full.get("requirements"):
        parts.append("דרישות:\n" + full["requirements"])
    return {
        "id": f"jobmaster:{card['key']}",
        "source": f"jobmaster:{company['slug']}",
        "company": card["company"] or HIDDEN_COMPANY,
        "title": card["title"],
        "url": url,
        "apply_url": url,
        "location": card["city"],
        "job_number": card["key"],
        "posted_at": None,
        "description": "\n\n".join(p for p in parts if p),
    }


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Jobs of every search path whose card matches a keyword (the whole site is Israel), and counts for the report."""
    cache = TextCache(cache_dir)
    by_id: dict[str, dict] = {}
    listed = 0
    for query in company["queries"]:
        for card in parse_cards(fetch_text(SEARCH.format(query=quote(query, safe="-")))):
            listed += 1
            if f"jobmaster:{card['key']}" in by_id:
                continue
            keyword = matching_keyword(card["title"], card["short"], keywords)
            if not keyword:
                continue
            full = cache.get(card["key"], lambda: parse_job_page(fetch_text(JOB.format(key=card["key"]))))
            job = to_job(card, full, company)
            job["matched_keyword"] = keyword
            by_id[job["id"]] = job
    jobs = list(by_id.values())
    return jobs, {"total": listed, "site_total": None, "israel": listed, "matched": len(jobs), "texts_fetched": cache.fetched}
