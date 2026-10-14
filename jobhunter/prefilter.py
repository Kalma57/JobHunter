"""Code prefilter before the brain (orchestrator.md, "סינון מוקדם בקוד").

The brain reads every job that reaches it, and that costs Claude Pro usage and time. Most new jobs fail on
something the code can see for sure in the title or in a plain number, so the code filters those first:

  field       the title names a field outside the search (sales, finance, hardware...) and no software role,
              or a field the search excludes even in software (QA, testing, support, teaching)
  degree      the title asks for a doctorate
  seniority   the title is senior / lead / manager... and has no student word
  experience  the title has no student word and the text asks for more years than the search allows

The words come from config/prefilter.json (data, like docs/search.md). Anything uncertain passes to the brain:
better a job the brain filters than a job the code swallowed. Filtered jobs are not lost - they are listed
in the run row on the board with their reason.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from jobhunter.agents.filters import matching_keyword

CONFIG = Path("config/prefilter.json")

# "3+ years of experience", "3-5 years of relevant hands-on experience", "minimum of 3 years experience"
YEARS_EN = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:[-–]\s*\d{1,2}\s*\+?\s*)?(?:or more\s+)?years?(?:['’]s?)?\s+(?:of\s+)?(?:[\w/+-]+\s+){0,5}?experience",
    re.I)
# "3 שנות ניסיון", "ניסיון של 3 שנים", "3+ שנים ניסיון", "ניסיון של לפחות 3 שנים"
YEARS_HE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:שנות|שנים)\s+(?:של\s+)?(?:ה)?ניסיון|ניסיון\s+(?:מוכח\s+)?(?:של\s+)?(?:לפחות\s+|מעל\s+)?(\d{1,2})\s*\+?\s*שנ")


@lru_cache(maxsize=None)
def load_rules(path: Path = CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def years_asked(text: str | None) -> int | None:
    """The smallest number of years of experience the text asks for, or None if it asks for none."""
    found = [int(g) for m in YEARS_EN.finditer(text or "") for g in m.groups() if g]
    found += [int(g) for m in YEARS_HE.finditer(text or "") for g in m.groups() if g]
    found = [n for n in found if 0 < n <= 30]
    return min(found) if found else None


def reject_reason(job: dict, rules: dict) -> str | None:
    """Why the code filters this job for sure, in Hebrew, or None if it goes to the brain."""
    title = job.get("title") or ""
    if word := matching_keyword(title, "", rules["always_field_title_words"]):
        return f"תחום אחר ({word} בשם המשרה)"
    software = matching_keyword(title, "", rules["software_title_words"])
    if not software and (word := matching_keyword(title, "", rules["field_title_words"])):
        return f"תחום אחר ({word} בשם המשרה)"
    if word := matching_keyword(title, "", rules["degree_title_words"]):
        return f"דורש תואר מתקדם ({word} בשם המשרה)"
    if matching_keyword(title, "", rules["student_title_words"]):
        return None
    if word := matching_keyword(title, "", rules["seniority_title_words"]):
        return f"משרה בכירה ({word} בשם המשרה)"
    years = years_asked(job.get("description"))
    if years is not None and years > rules["max_years_experience"]:
        return f"דורש {years}+ שנות ניסיון"
    return None


def split(jobs: list[dict], rules: dict) -> tuple[list[dict], list[dict]]:
    """(jobs for the brain, filtered jobs each with "prefilter_reason")."""
    keep, out = [], []
    for job in jobs:
        reason = reject_reason(job, rules)
        if reason:
            out.append({**job, "prefilter_reason": reason})
        else:
            keep.append(job)
    return keep, out
