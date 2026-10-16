"""The user's marks from the public site (16/10/2026): statuses.json on the repo's board-data branch.

The site (site/public.html) lets the owner mark jobs - applied, on hold, not interested, notes, an apply link -
and saves them through the GitHub API to statuses.json on the board-data branch, one entry per board job:
    {"<doc_id>": {"status": "applied", "history": [{status, at, note}], "notes": "...", "applied_at": "...", ...}}

The board's cards (written by the brain) stay in the claude.ai board database. Wherever the code needs a job's
status, it reads the card with the overlay on top (merge): the user's status counts unless the card has a newer
event, so a "closed" the morning run writes after the user's "hold" wins, and a later "back to new" wins again.
The same merge runs in the page (site/public.html, mergeOverlay).
"""

import json
import subprocess

BRANCH = "board-data"
FILE = "statuses.json"
USER_FIELDS = ("notes", "applied_at", "apply_channel", "applied_description", "not_interested_reason", "apply_url")


def load(cwd: str | None = None) -> tuple[dict, str | None]:
    """(overlay, error) - fetched from origin's board-data branch. An empty overlay when the branch is missing."""
    def git(*args: str):
        return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)

    done = git("fetch", "-q", "origin", BRANCH)
    if done.returncode != 0:
        return {}, f"board-data: {(done.stdout + done.stderr).strip()[-200:]}"
    done = git("show", f"FETCH_HEAD:{FILE}")
    if done.returncode != 0:
        return {}, f"board-data: {FILE} missing"
    try:
        return json.loads(done.stdout or "{}"), None
    except json.JSONDecodeError as e:
        return {}, f"board-data: {FILE} is not JSON ({e})"


def merge(job: dict, mark: dict | None) -> dict:
    """The card with the user's marks on top; the latest event of both histories sets the status."""
    if not mark:
        return job
    card_history = list(job.get("history") or [])
    seen = {(h.get("at"), h.get("status")) for h in card_history}
    history = card_history + [h for h in mark.get("history") or [] if (h.get("at"), h.get("status")) not in seen]
    card_last = max((h.get("at") or "" for h in card_history), default="")
    mark_last = max((h.get("at") or "" for h in mark.get("history") or []), default="")
    out = {**job, **{k: mark[k] for k in USER_FIELDS if k in mark}, "history": history}
    if mark.get("status") and mark_last >= card_last:
        out["status"] = mark["status"]
    return out


def apply(board: dict[str, dict], overlay: dict) -> dict[str, dict]:
    return {doc_id: merge(job, overlay.get(doc_id)) for doc_id, job in board.items()}
