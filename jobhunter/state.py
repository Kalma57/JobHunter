"""Storage between morning runs (stage 5).

SeenStore  one sub-agent's memory: which job ids it has already seen, and when it last saw each.
           Lives in state/seen/<agent>.json. Lets the sub-agent pass on only jobs it has never seen.
Inbox      the day's new jobs, collected by all sub-agents for the brain.
           Lives in state/inbox/<YYYY-MM-DD>.json.

Every job dict carries an "id" that is unique per source, e.g. "lever:mobileye:60ebea6b-...".
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

PRUNE_AFTER_DAYS = 30  # an id not seen on the site for this long is forgotten (orchestrator.md)


def _write_json(path: Path, data) -> None:
    """Write via a temp file and rename, so a crash mid-write never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class SeenStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._last_seen: dict[str, str] = _read_json(self.path, {})

    def __len__(self) -> int:
        return len(self._last_seen)

    def is_new(self, job_id: str) -> bool:
        return job_id not in self._last_seen

    def mark_seen(self, job_id: str, today: date) -> None:
        """Record that the job is on the site today (also refreshes ids we already knew)."""
        self._last_seen[job_id] = today.isoformat()

    def prune(self, today: date, days: int = PRUNE_AFTER_DAYS) -> list[str]:
        """Forget ids not seen for more than `days` days. Returns the forgotten ids."""
        cutoff = (today - timedelta(days=days)).isoformat()
        old = [job_id for job_id, seen in self._last_seen.items() if seen < cutoff]
        for job_id in old:
            del self._last_seen[job_id]
        return old

    def save(self) -> None:
        _write_json(self.path, self._last_seen)


class Inbox:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, day: date) -> Path:
        return self.directory / f"{day.isoformat()}.json"

    def read(self, day: date) -> list[dict]:
        return _read_json(self._path(day), [])

    def add(self, day: date, jobs: list[dict]) -> int:
        """Append jobs to the day's file, skipping ids already in it. Returns how many were added."""
        current = self.read(day)
        known = {job["id"] for job in current}
        added = [job for job in jobs if job["id"] not in known]
        if added:
            _write_json(self._path(day), current + added)
        return len(added)


def collect_new(jobs: list[dict], seen: SeenStore, inbox: Inbox, today: date) -> int:
    """One sub-agent's daily hand-off: new jobs go to the inbox, every job on the site is marked seen.

    Returns how many jobs reached the inbox.
    """
    new_jobs = [job for job in jobs if seen.is_new(job["id"])]
    added = inbox.add(today, new_jobs)
    for job in jobs:
        seen.mark_seen(job["id"], today)
    seen.prune(today)
    seen.save()
    return added
