"""Sitemap agent (21/10/2026): career sites whose search is closed to tools but whose sitemap lists every job.

Intuit and Synopsys (Radancy / TalentBrew sites) ask tools not to use /search-jobs/ (robots.txt), but publish
/sitemap.xml - the file a site writes for crawlers - with a link to every open job:
    https://<host>/job/<city>/<title-slug>/<org>/<job id>
So the agent reads the sitemap, keeps the jobs whose city is in Israel (config "cities", URL slugs), and opens
each such job page once (cache.py). The page carries the posting as JSON-LD (schema.org JobPosting): title, full
description, date and place. Keywords are checked on the title and the text, like every other agent.
"""

import json
import re
from pathlib import Path

from jobhunter.agents.cache import TextCache
from jobhunter.agents.filters import html_to_text, matching_keyword
from jobhunter.agents.http import FetchError, fetch_text

ISRAEL_CITIES = ["israel", "tel-aviv", "petah-tikva", "petach-tikva", "herzliya", "haifa", "raanana", "ra-anana", "hod-hasharon",
                 "beer-sheva", "beersheba", "jerusalem", "yokneam", "kfar-saba", "netanya", "rehovot", "airport-city",
                 "caesarea", "kiryat-gat", "ramat-gan", "glil-yam", "or-yehuda", "modiin", "ness-ziona", "rosh-haayin"]
LD_JSON = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)


def job_urls(sitemap_xml: str, host: str, cities: list[str]) -> list[str]:
    city = "|".join(re.escape(c) for c in cities)
    pattern = re.compile(rf"https://{re.escape(host)}/job/(?:{city})/[^<\s]+", re.I)
    return list(dict.fromkeys(pattern.findall(sitemap_xml)))


def job_posting(html: str) -> dict:
    """The page's schema.org JobPosting, or {} when the page has none."""
    for block in LD_JSON.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                places = item.get("jobLocation") or []
                places = places if isinstance(places, list) else [places]
                where = [", ".join(p for p in ((pl.get("address") or {}).get("addressLocality"), (pl.get("address") or {}).get("addressCountry")) if p)
                         for pl in places if isinstance(pl, dict)]
                return {"title": item.get("title"), "description": html_to_text(item.get("description")),
                        "posted_at": (item.get("datePosted") or "")[:10] or None, "location": "; ".join(w for w in where if w),
                        "job_number": (item.get("identifier") or {}).get("value") if isinstance(item.get("identifier"), dict) else None}
    return {}


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    host = company["host"]
    urls = job_urls(fetch_text(f"https://{host}/sitemap.xml"), host, company.get("cities", ISRAEL_CITIES))
    texts = TextCache(cache_dir)
    jobs = []
    for url in urls:
        job_id = url.rstrip("/").rsplit("/", 1)[-1]
        posting = texts.get(job_id, lambda: job_posting(fetch_text(url)))
        if not posting.get("title"):
            continue
        job = {
            "id": f"sitemap:{company['slug']}:{job_id}",
            "source": f"sitemap:{company['slug']}",
            "company": company["company"],
            "title": posting["title"].strip(),
            "url": url,
            "apply_url": url,
            "location": posting.get("location") or url.split("/job/")[1].split("/")[0].replace("-", " ").title(),
            "job_number": posting.get("job_number"),
            "posted_at": posting.get("posted_at"),
            "description": posting.get("description") or "",
        }
        keyword = matching_keyword(job["title"], job["description"], keywords)
        if keyword:
            job["matched_keyword"] = keyword
            jobs.append(job)
    if not urls and company.get("expect_jobs"):
        raise FetchError("the sitemap lists no jobs in Israel - the site may have changed")
    texts.keep_only({u.rstrip("/").rsplit("/", 1)[-1] for u in urls})
    return jobs, {"total": len(urls), "site_total": None, "israel": len(urls), "matched": len(jobs), "texts_fetched": texts.fetched}
