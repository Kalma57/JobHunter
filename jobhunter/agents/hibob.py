"""HiBob agent (stage 8, tier 2): www.hibob.com/careers.

HiBob moved its jobs from Comeet to its own recruiting product (careers.hibob.com). That site's API needs
sign-in (401), so the agent reads only the public careers page, which lists every job with its title,
department, employment type and site (<li data-site=.. data-department=..> + <a href=".../jobs/<uuid>">).
There is no full text: a job reaches the brain with these card details and a link, like HireMeTech after its
sign-in wall.
"""

import re
from html import unescape

from jobhunter.agents.filters import is_israel, matching_keyword
from jobhunter.agents.http import fetch_text

PAGE = "https://www.hibob.com/careers/"
JOB = re.compile(
    r'<li class="hibob-careers__job"(?P<attrs>[^>]*)>\s*'
    r'<a [^>]*href="(?P<url>https://[a-z0-9-]+\.careers\.hibob\.com/jobs/(?P<id>[0-9a-f-]{36}))"[^>]*>\s*'
    r'<span [^>]*position-title[^>]*>(?P<title>.*?)</span>\s*'
    r'<span [^>]*position-meta[^>]*>(?P<meta>.*?)</span>', re.S)
TEXT_HIDDEN_NOTE = "(הטקסט המלא של המשרה זמין רק באתר המשרות של HiBob — מוצגים הפרטים מעמוד הקריירה.)"


def parse_jobs(html: str) -> list[dict]:
    jobs = []
    for m in JOB.finditer(html):
        attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', m.group("attrs")))
        meta = unescape(re.sub(r"\s+", " ", m.group("meta"))).strip()  # "Permanent | Israel"
        jobs.append({"id": m.group("id"), "url": m.group("url"), "title": unescape(m.group("title")).strip(),
                     "site": unescape(attrs.get("site", "")), "department": unescape(attrs.get("department", "")),
                     "meta": meta})
    return jobs


def to_job(card: dict, company: dict) -> dict:
    location = card["site"] or card["meta"].split("|")[-1].strip()
    return {
        "id": f"hibob:{card['id']}",
        "source": f"hibob:{company['slug']}",
        "company": company["company"],
        "title": card["title"],
        "url": card["url"],
        "apply_url": card["url"],
        "location": location,
        "job_number": None,
        "posted_at": None,
        "description": f"{card['title']}\n{card['department']}\n{card['meta']}\n\n{TEXT_HIDDEN_NOTE}",
    }


def fetch(company: dict, israel: dict, keywords: list[str]) -> tuple[list[dict], dict]:
    """Jobs in Israel that match a keyword (title / department / employment type), and counts for the run report."""
    cards = parse_jobs(fetch_text(company.get("page", PAGE)))
    jobs, in_israel = [], 0
    for card in cards:
        job = to_job(card, company)
        if not is_israel(job["location"], None, israel):
            continue
        in_israel += 1
        keyword = matching_keyword(job["title"], job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    stats = {"total": len(cards), "site_total": None, "israel": in_israel, "matched": len(jobs)}
    return jobs, stats
