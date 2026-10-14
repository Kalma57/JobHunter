"""The public page (docs/public-page.md): a static page that shows what the morning run found, for a link on LinkedIn.

    python -m jobhunter.public build [--board-dir state/board] [--state state]   (also runs inside `morning finish`)

Built from the board snapshot taken after the morning writes, so it needs no server and no Claude: the template
site/public.html + the data as JSON -> public/index.html. Anyone with the link sees it, so it shows only:
  - jobs that passed the search and are still open (title, company, place, fit, link) - never a status, a note,
    an application, or anything else the user marked on the board
  - the run's numbers: sources read, jobs scanned, filtered by code, read by the brain
The owner's name and links come from config/public.json.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from jobhunter.state import _read_json

TEMPLATE = Path("site/public.html")
CONFIG = Path("config/public.json")
OUT_DIR = Path("public")
HIDDEN_STATUSES = {"filtered", "closed", "not_interested"}  # the rest (new, hold, applied...) look the same in public
JOB_FIELDS = ("title", "company", "location", "work_mode", "scope", "rank", "first_seen", "posted_at", "deadline")
BOARD_SOURCES = ("hiremetech:", "drushim:", "jobmaster:")


def public_jobs(board: dict[str, dict]) -> list[dict]:
    out = []
    for job in board.values():
        if job.get("status") in HIDDEN_STATUSES or job.get("compacted") or not (job.get("relevance") or {}).get("pass"):
            continue
        if not job.get("agent_id"):  # the hand-made test set, not real jobs from this morning's sources
            continue
        item = {k: job.get(k) for k in JOB_FIELDS}
        item["url"] = job.get("url")
        item["tags"] = list(job.get("prefs_up") or [])
        item["summary"] = job.get("description") if len(job.get("description") or "") <= 220 else None
        item["via_board"] = (job.get("source") or "").startswith(BOARD_SOURCES)
        out.append(item)
    rank = {"high": 0, "mid": 1, "low": 2}
    out.sort(key=lambda j: j.get("first_seen") or "", reverse=True)  # newest first...
    out.sort(key=lambda j: rank.get(j.get("rank"), 3))                # ...within each fit level
    return out


def run_numbers(state: Path, today: date) -> dict:
    report = _read_json(state / "runs" / f"{today.isoformat()}-agents.json", {})
    run = _read_json(state / "plan" / f"{today.isoformat()}-run.json", {})
    companies = report.get("companies", [])
    return {
        "date": today.isoformat(),
        "sources_total": len(companies),
        "sources_read": sum(1 for c in companies if "error" not in c),
        "scanned": sum(c.get("israel") or 0 for c in companies),
        "matched": sum(c.get("matched") or 0 for c in companies),
        "new": report.get("new", 0),
        "candidates": run.get("candidates", 0),
        "after_prefilter": run.get("after_prefilter", 0),
        "prefiltered": run.get("prefiltered_count", 0),
        "to_brain": run.get("to_brain", 0),
        "companies": sorted({c["company"] for c in companies if "error" not in c}),
    }


def build(board_dir: Path, state: Path, today: date, out_dir: Path = OUT_DIR) -> dict:
    from jobhunter.morning import load_board
    board = load_board(board_dir)
    data = {"config": _read_json(CONFIG, {}), "run": run_numbers(state, today), "jobs": public_jobs(board)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return {"path": str((out_dir / "index.html").resolve()), "jobs": len(data["jobs"]), "sources_read": data["run"]["sources_read"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunter.public")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cmd = sub.add_parser("build")
    cmd.add_argument("--board-dir", type=Path, default=Path("state/board"))
    cmd.add_argument("--state", type=Path, default=Path("state"))
    cmd.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(build(args.board_dir, args.state, args.today), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
