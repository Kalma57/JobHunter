"""Job texts fetched once per job (stage 8): for systems whose job list has no text (Workday, Eightfold, SmartRecruiters, Oracle).

Each job's details are kept as <directory>/<key>.json and deleted when the job leaves the site, so after the
first run a morning costs only the list plus the jobs posted since yesterday, and the weekly scan needs no
extra requests. With directory=None (tests, one-off runs) nothing is kept.
"""

import json
from pathlib import Path
from typing import Callable

from jobhunter.state import _write_json


class TextCache:
    def __init__(self, directory: Path | None):
        self.directory = Path(directory) if directory else None
        self.fetched = 0  # how many texts came from the site this run (for the run report)

    def get(self, key: str, fetch: Callable[[], dict]) -> dict:
        path = self.directory / f"{key}.json" if self.directory else None
        if path and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        detail = fetch()
        self.fetched += 1
        if path:
            _write_json(path, detail)
        return detail

    def keep_only(self, keys: set[str]) -> None:
        """Forget the texts of jobs that are no longer listed. Call only after the full list was read."""
        if not self.directory or not self.directory.exists():
            return
        for path in self.directory.glob("*.json"):
            if path.stem not in keys:
                path.unlink()
