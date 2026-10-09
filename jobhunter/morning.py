"""The code half of the morning orchestrator run (stage 6).

    python -m jobhunter.morning plan --board-dir <dir> --today YYYY-MM-DD

<dir> holds a snapshot of the board's jobs (one <id>.json per job, as ArtifactData saves them with
out_dir, under <dir>/jobs/). The plan is printed and saved to state/plan/<date>.json:

  jobs         every inbox job, with its duplicate candidates on the board (or earlier in today's inbox)
  compactions  board jobs that the 30-day rule shrinks today

The brain then reads the plan: it builds cards only for jobs without an exact match, decides the
borderline ones, and writes everything to the board.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from jobhunter.dedup import find_matches
from jobhunter.retention import compaction_update
from jobhunter.state import Inbox


def load_board(board_dir: Path) -> dict[str, dict]:
    jobs_dir = board_dir / "jobs"
    if not jobs_dir.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(jobs_dir.glob("*.json"))}


def build_plan(board: dict[str, dict], inbox_jobs: list[dict], today: date) -> dict:
    planned = []
    seen_today: dict[str, dict] = {}
    for job in inbox_jobs:
        matches = find_matches(job, board) + find_matches(job, seen_today)
        planned.append({
            "inbox_job": job,
            "matches": [
                {**asdict(m), "board_status": (board.get(m.board_id) or {}).get("status", "today")}
                for m in matches
            ],
        })
        seen_today[f"inbox:{job['id']}"] = job
    compactions = [
        {"board_id": board_id, "update": update}
        for board_id, job in board.items()
        if (update := compaction_update(job, today)) is not None
    ]
    return {"date": today.isoformat(), "jobs": planned, "compactions": compactions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunter.morning")
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan_cmd = sub.add_parser("plan")
    plan_cmd.add_argument("--board-dir", type=Path, required=True)
    plan_cmd.add_argument("--today", type=date.fromisoformat, default=date.today())
    plan_cmd.add_argument("--state", type=Path, default=Path("state"))
    args = parser.parse_args(argv)

    plan = build_plan(load_board(args.board_dir), Inbox(args.state / "inbox").read(args.today), args.today)
    out = args.state / "plan" / f"{args.today.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
