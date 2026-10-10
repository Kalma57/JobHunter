"""HireMeTech agent (stage 9): the juniors job board, juniors.hiremetech.com (Israel only).

Why a real browser: the job pages are allowed by the site's robots.txt, but they arrive empty and load their
content from /api/, which robots.txt asks automated tools not to call. So we never call /api/ ourselves:
Playwright opens the allowed pages (the job list sorted by date, and single job pages) in a background
Chromium, the page loads its own content as it does for any visitor, and we read the text on the screen.

Daily: read the list newest-first, page by page, until a page holds only jobs we already know (or max_pages).
Keywords are checked on each card's title and tags ("Student / Intern"); only cards that match get their
job page opened (once - the text is kept in <cache_dir>/cards.json). The list has no full text, so a job
whose card says nothing about students is not caught here; the company agents and the weekly scan cover more.
The company name is hidden from visitors who are not signed in, so `company` is "חסוי — דרך HireMeTech".

Playwright is imported only when the agent runs, so the rest of the code and the tests don't need it.
"""

import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from jobhunter.agents.filters import matching_keyword
from jobhunter.state import _read_json, _write_json

USER_AGENT = "JobHunter/1.0 (personal job search; read-only; one request at a time)"
LIST_URL = "https://{host}/jobs-app?view=jobs&sort_by=posted_date&sort_order=desc&page={page}"
JOB_URL = "https://{host}/job/{job_id}"
PAUSE_SECONDS = 1.0
FORGET_AFTER_DAYS = 60  # cached cards older than this are dropped (the list never goes back that far)
HIDDEN_COMPANY = "חסוי — דרך HireMeTech"

BADGES = {"Fresh", "New", "טרי", "חדש", "Hot", "חם"}
TEXT_STARTS = ("על התפקיד", "About the role", "About the Role")
TEXT_ENDS = ("משרות דומות", "Similar jobs", "Similar Jobs", "פרטים נוספים", "Additional details")
POSTED_LINE = re.compile(r"^(?:פורסם|Posted)\s*$")
# After a few job pages the site asks visitors to sign in "to verify a real user and filter bots". That is a
# block, so we don't get past it: from that point the job is passed on with its card only.
LOGIN_WALL = ("התחבר כדי להגיש", "Sign in to apply", "Log in to apply")
TEXT_HIDDEN_NOTE = "(הטקסט המלא של המשרה זמין באתר רק למשתמשים מחוברים — מוצגים פרטי הכרטיס מהרשימה.)"


def parse_card(text: str) -> dict:
    """A job card from the list -> title, location, and the whole card text (its tags count for keywords)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if line not in BADGES]
    title = lines[0] if lines else ""
    location = ""
    if "·" in lines:
        after = lines[lines.index("·") + 1:]
        location = after[0] if after else ""
    return {"title": title, "location": location, "card": "\n".join(lines)}


def parse_job_page(text: str) -> dict | None:
    """A job page's screen text -> the job text (from "About the role" to "Similar jobs") and the posting date.
    None when the page shows the sign-in wall instead of the job."""
    if any(marker in text for marker in LOGIN_WALL):
        return None
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() in TEXT_STARTS), None)
    end = next((i for i, line in enumerate(lines) if start is not None and i > start and line.strip() in TEXT_ENDS), len(lines))
    body = "\n".join(lines[start + 1:end] if start is not None else lines)
    description = re.sub(r"\n{3,}", "\n\n", body).strip()
    posted_at = None
    for i, line in enumerate(lines[:-1]):
        if POSTED_LINE.match(line.strip()):
            try:
                posted_at = datetime.strptime(lines[i + 1].strip(), "%b %d, %Y").date().isoformat()
            except ValueError:
                pass
    return {"description": description, "posted_at": posted_at}


def to_job(job_id: str, card: dict, company: dict) -> dict:
    url = JOB_URL.format(host=company["host"], job_id=job_id)
    return {
        "id": f"hiremetech:{job_id}",
        "source": f"hiremetech:{company['slug']}",
        "company": HIDDEN_COMPANY,
        "title": card["title"],
        "url": url,
        "apply_url": url,
        "location": card.get("location") or "",
        "job_number": None,
        "posted_at": card.get("posted_at"),
        "description": card.get("description") or "",
    }


def collect(read_list_page, read_job_page, company: dict, keywords: list[str], cache_dir: Path | None,
            today: date, max_pages: int) -> tuple[list[dict], dict]:
    """The agent without the browser: read_list_page(n) -> [(job_id, card_text)], read_job_page(job_id) -> screen text."""
    cache_path = cache_dir / "cards.json" if cache_dir else None
    cache: dict[str, dict] = _read_json(cache_path, {}) if cache_path else {}
    known_before = set(cache)
    listed_today: list[str] = []
    pages = 0
    for page in range(1, max_pages + 1):
        cards = read_list_page(page)
        pages += 1
        if not cards:
            break
        for job_id, text in cards:
            if job_id not in cache:
                cache[job_id] = {**parse_card(text), "first_seen": today.isoformat()}
            if job_id not in listed_today:
                listed_today.append(job_id)
        if all(job_id in known_before for job_id, _ in cards):
            break  # this page and everything after it was read on an earlier day

    jobs, fetched, walled = [], 0, False
    for job_id in listed_today:
        card = cache[job_id]
        keyword = matching_keyword(card["title"], card["card"], keywords)
        if not keyword:
            continue
        if "description" not in card:
            parsed = None if walled else parse_job_page(read_job_page(job_id))
            fetched += not walled
            if parsed is None:  # sign-in wall: stop opening job pages this run, pass the card on
                walled = True
                parsed = {"description": f"{card['card']}\n\n{TEXT_HIDDEN_NOTE}", "posted_at": None, "text_hidden": True}
            card.update(parsed)
        job = to_job(job_id, card, company)
        job["matched_keyword"] = keyword
        jobs.append(job)

    if cache_path:
        cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
        _write_json(cache_path, {k: v for k, v in cache.items() if v["first_seen"] >= cutoff})
    stats = {"total": len(listed_today), "site_total": None, "israel": len(listed_today),  # the site lists Israel only
             "matched": len(jobs), "pages": pages, "texts_fetched": fetched, "sign_in_wall": walled}
    return jobs, stats


def fetch(company: dict, israel: dict, keywords: list[str], cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Open the board in a background browser and collect. Raises on a page that can't be loaded (the runner skips us)."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT)

            def open_page(url: str) -> None:
                time.sleep(PAUSE_SECONDS)
                page.goto(url, wait_until="networkidle", timeout=60_000)

            def read_list_page(n: int) -> list[tuple[str, str]]:
                open_page(LIST_URL.format(host=company["host"], page=n))
                try:  # the list renders after the network goes quiet; an empty page only after a real wait
                    page.wait_for_selector('a[href*="/job/"]', timeout=20_000)
                except PlaywrightTimeout:
                    return []
                found = page.eval_on_selector_all(
                    'a[href*="/job/"]',
                    "els => els.map(e => [e.getAttribute('href'), (e.closest('div[class]') || e).innerText])")
                cards = []
                for href, text in found:
                    m = re.search(r"/job/(\d+)", href or "")
                    if m:
                        cards.append((m.group(1), text))
                return cards

            def read_job_page(job_id: str) -> str:
                open_page(JOB_URL.format(host=company["host"], job_id=job_id))
                return page.inner_text("body")

            return collect(read_list_page, read_job_page, company, keywords, cache_dir,
                           date.today(), company.get("max_pages", 40))
        finally:
            browser.close()
