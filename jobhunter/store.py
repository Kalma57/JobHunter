"""The board's store (6/11/2026): one JSON file per job in state/board/jobs/, kept in git.

Until now the board lived in the claude.ai board's database, so every board write went through a tool of the
Claude app, and the unattended runs kept stopping on that tool's approval prompts. Now the code writes the board
itself, and Claude (`claude -p`, docs/agents/brain-run.md) only reads the day's jobs and writes one file of cards.

apply_writes   the code's own writes (sightings, closures, the 30-day rule, deletions) - from split_plan
apply_cards    the brain's cards: a new board job each, or a duplicate merged into an existing job
The user's marks (statuses.json, overlay.py) stay where they are and are laid on top when the board is read.
"""

import json
from pathlib import Path

from jobhunter.state import _read_json, _write_json

DELETE = "__delete__"


def _job_path(board_dir: Path, doc_id: str) -> Path:
    return board_dir / "jobs" / f"{doc_id}.json"


def _merge(doc: dict, data: dict) -> dict:
    out = dict(doc)
    for key, value in data.items():
        if isinstance(value, dict) and value.get(DELETE):
            out.pop(key, None)
        else:
            out[key] = value
    return out


def apply_writes(board_dir: Path, writes: list[dict]) -> dict:
    """update = merge the fields ({"__delete__": true} removes one), delete = remove the job. Returns counts."""
    counts = {"updated": 0, "deleted": 0, "missing": 0}
    for w in writes:
        path = _job_path(board_dir, w["doc_id"])
        if w["op"] == "delete":
            if path.exists():
                path.unlink()
                counts["deleted"] += 1
            continue
        if not path.exists():
            counts["missing"] += 1
            continue
        _write_json(path, _merge(_read_json(path, {}), w["data"]))
        counts["updated"] += 1
    return counts


def apply_cards(board_dir: Path, brain: list[dict], cards: list[dict], day: str) -> tuple[dict, list[dict]]:
    """The brain's cards onto the board. Returns (counts, the brain jobs that got no card - they go back to the queue).

    A card with "duplicate_of" = the brain judged a borderline pair to be one job: the board job gets the new
    sightings and an alert, its status untouched. Any other card becomes a new board job: the card's fields, the
    code's fields (agent_id, source, first_seen, sightings, notes) and its first history line.
    """
    by_id = {c.get("doc_id"): c for c in cards if isinstance(c, dict) and c.get("doc_id")}
    for c in by_id.values():  # a twin from this same morning is named "inbox:<agent id>" in the brain file
        if str(c.get("duplicate_of") or "").startswith("inbox:"):
            c["duplicate_of"] = c["duplicate_of"].removeprefix("inbox:").replace(":", "-")
    # new jobs first, so a duplicate of a job from this same morning finds it on the board
    brain = sorted(brain, key=lambda e: 1 if (by_id.get(e["doc_id"]) or {}).get("duplicate_of") else 0)
    counts = {"passed": 0, "brain_filtered": 0, "far": 0, "merged": 0, "no_card": 0}
    borderline_notes, missing = [], []
    for entry in brain:
        card = by_id.get(entry["doc_id"])
        if card is None:
            counts["no_card"] += 1
            missing.append(entry)
            continue
        target = card.get("duplicate_of")
        if target and _job_path(board_dir, target).exists():
            path = _job_path(board_dir, target)
            existing = _read_json(path, {})
            existing["sightings"] = list(existing.get("sightings") or []) + list(entry["fields"]["sightings"])
            existing["alerts"] = list(existing.get("alerts") or []) + ["אוחדה עם משרה דומה — בדוק"]
            _write_json(path, existing)
            counts["merged"] += 1
            borderline_notes.append(f"{entry['job'].get('title')} — כפילות של {target}: {card.get('duplicate_reason', '')}")
            continue
        status = "new" if card.get("status") == "new" else "filtered"
        doc = {k: v for k, v in card.items() if k not in ("doc_id", "duplicate_of", "duplicate_reason")}
        doc.update(entry["fields"])
        doc["status"] = status
        doc["history"] = [{"status": status, "at": f"{day}T07:00:00Z", "note": entry["history_note"]}]
        _write_json(_job_path(board_dir, entry["doc_id"]), doc)
        if entry.get("borderline"):
            borderline_notes.append(f"{entry['job'].get('title')} — לא כפילות")
        if status == "new":
            counts["passed"] += 1
        else:
            counts["brain_filtered"] += 1
            counts["far"] += 1 if card.get("far") else 0
    counts["borderline"] = borderline_notes
    return counts, missing


def read_cards(path: Path) -> list[dict]:
    """The brain's file: {"cards": [...]} (a bare list is accepted too). A broken file reads as no cards."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("cards", []) if isinstance(data, dict) else data if isinstance(data, list) else []
