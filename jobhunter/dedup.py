"""Duplicate detection for the orchestrator (stage 6).

Code decides only what is certain. Everything uncertain is returned as "borderline" for the brain.

exact       same job for sure: same normalized link, or same job number at the same company,
            or same company + same title words + same location
borderline  maybe the same job: same title words (or very close) and the company is equal
            or unknown/hidden on one side. The brain decides.

Never a duplicate on its own: same company with a different role (Amazon Virtual Platforms vs SPIV).
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that identify a job on some sites; every other parameter (utm_*, ref...) is noise.
ID_PARAMS = {"gh_jid", "jobid", "job_id", "id", "jk", "jid"}

# Words that say nothing about which role it is.
TITLE_NOISE = {
    "junior", "jr", "student", "students", "position", "intern", "internship", "senior", "sr",
    "the", "a", "an", "and", "for", "of", "with", "at", "in", "to", "-", "–",
    "סטודנט", "סטודנטית", "משרת", "משרה", "גוניור", "ג'וניור", "דרוש", "דרושה", "דרושים", "ל", "עבור", "עם", "ב",
}

HIDDEN_COMPANY = re.compile(r"חסוי|confidential|undisclosed|leading|מובילה", re.I)

JOB_NUMBER = re.compile(r"(?:מספר משרה|משרה מס['׳]?|job\s*(?:id|number|#)|req(?:uisition)?\s*(?:id|#)?)\s*[:#]?\s*([A-Za-z0-9-]{3,})", re.I)

BORDERLINE_SIMILARITY = 0.6


@dataclass(frozen=True)
class Match:
    board_id: str
    kind: str  # "exact" | "borderline"
    reason: str


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    query = sorted((k.lower(), v) for k, v in parse_qsl(parts.query) if k.lower() in ID_PARAMS)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return urlunsplit(("https", host, path, urlencode(query), ""))


def job_number(job: dict) -> str | None:
    if job.get("job_number"):
        return str(job["job_number"]).strip().lower()
    for field in ("description", "raw_text"):
        m = JOB_NUMBER.search(job.get(field) or "")
        if m:
            return m.group(1).lower()
    return None


def _clean(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[./]ית\b|/[תה]\b|\(ת\)", "", text)  # Hebrew gender endings: מפתח/ת, סטודנט.ית
    return re.sub(r"[^\w\s']+", " ", text)


def title_words(title: str | None) -> frozenset[str]:
    return frozenset(w for w in _clean(title or "").split() if w not in TITLE_NOISE)


def company_key(company: str | None) -> str | None:
    """None when the company is unknown or hidden — such a job can only ever be a borderline match."""
    if not company or HIDDEN_COMPANY.search(company):
        return None
    first = re.split(r"[(\-—|]", company)[0]  # "Amazon (Annapurna Labs)" -> "amazon"
    words = _clean(first).split()
    return " ".join(w for w in words if w not in {"ltd", "inc", "group", "technologies", "systems"}) or None


def _similarity(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_matches(job: dict, board: dict[str, dict]) -> list[Match]:
    """Compare one incoming job with every job already on the board. Exact matches first."""
    url = normalize_url(job.get("url"))
    number = job_number(job)
    company = company_key(job.get("company"))
    words = title_words(job.get("title"))
    location = _clean(job.get("location") or "").strip()

    exact, borderline = [], []
    for board_id, other in board.items():
        other_company = company_key(other.get("company"))
        same_company = company is not None and company == other_company
        if url and url == normalize_url(other.get("url")):
            exact.append(Match(board_id, "exact", "אותו קישור"))
            continue
        if number and same_company and number == job_number(other):
            exact.append(Match(board_id, "exact", f"אותו מספר משרה ({number})"))
            continue
        sim = _similarity(words, title_words(other.get("title")))
        other_location = _clean(other.get("location") or "").strip()
        if same_company and sim == 1.0 and location and location == other_location:
            exact.append(Match(board_id, "exact", "אותה חברה, אותו תפקיד ואותו מיקום"))
            continue
        company_unknown = company is None or other_company is None
        if sim >= BORDERLINE_SIMILARITY and (same_company or company_unknown):
            borderline.append(Match(board_id, "borderline", f"תפקיד דומה ({sim:.0%}), חברה {'זהה' if same_company else 'לא ידועה באחד הצדדים'}"))
    return exact + borderline
