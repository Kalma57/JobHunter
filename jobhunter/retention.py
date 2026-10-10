"""The 30-day rule (orchestrator.md, "שמירה ומחיקה").

Applied / on hold / after applying: kept forever, in full.
Not interested / closed / filtered / new-but-untouched: after 30 days without a status change the heavy
text is removed and a short line stays (title, company, link, dates, status, reason, notes), so the job
can still be found and never comes back as new.
Far (filtered only because of its location, `far: true`): kept in full while the job is still open on the
site - the user may want it some day (decision 10/10/2026). Once it closes, the 30 days apply.
"""

from datetime import date, datetime

COMPACT_AFTER_DAYS = 30
KEEP_FOREVER = {"applied", "interview", "offer", "rejected", "hold"}
HEAVY_FIELDS = (
    "description", "requirements_must", "requirements_adv", "apply_instructions",
    "education", "inferred", "not_stated", "prefs_up", "prefs_down", "applied_description",
)


def last_change(job: dict) -> date | None:
    stamps = [h.get("at") for h in job.get("history") or [] if h.get("at")]
    if job.get("first_seen"):
        stamps.append(job["first_seen"])
    if not stamps:
        return None
    return max(datetime.fromisoformat(s.replace("Z", "+00:00")).date() for s in stamps)


def compaction_update(job: dict, today: date) -> dict | None:
    """The update that shrinks this job to its short line, or None if it should stay as is."""
    if job.get("status") in KEEP_FOREVER or job.get("compacted"):
        return None
    if job.get("far") and job.get("status") == "filtered":  # still open: keep it whole
        return None
    changed = last_change(job)
    if changed is None or (today - changed).days <= COMPACT_AFTER_DAYS:
        return None
    update = {field: {"__delete__": True} for field in HEAVY_FIELDS if field in job}
    update["compacted"] = today.isoformat()
    return update
