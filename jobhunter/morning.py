"""The code half of the morning orchestrator run (stage 6).

    python -m jobhunter.morning plan --board-dir <dir> --today YYYY-MM-DD

<dir> holds a snapshot of the board's jobs (one <id>.json per job, as ArtifactData saves them with
out_dir, under <dir>/jobs/). The plan is printed and saved to state/plan/<date>.json:

  jobs         today's share of the inbox (at most DAILY_LIMIT), each with its duplicate candidates on the
               board (or earlier in today's share)
  backlog      how many jobs wait for the next mornings
  compactions  board jobs that the 30-day rule shrinks today

The brain reads every job of the plan, which costs Claude Pro usage, so one morning takes at most DAILY_LIMIT
jobs (user's decision, 10/10/2026). The rest wait in state/inbox/backlog.json and go first the next morning.
Order: student / intern in the title, then only in the text, then the rest; company sites before job boards; newest first.

The brain then reads the plan: it builds cards only for jobs without an exact match, decides the
borderline ones, and writes everything to the board.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from jobhunter.agents.filters import matching_keyword
from jobhunter.dedup import find_matches
from jobhunter.retention import compaction_update
from jobhunter.state import Inbox, _read_json, _write_json

DAILY_LIMIT = 40
DAILY_KEYWORDS = {"Student", "Intern", "Internship", "סטודנט"}
BOARD_SOURCES = ("hiremetech:",)  # job boards: often card details only, and many repeat company-site jobs


def priority(job: dict) -> tuple:
    """Sort key: student/intern in the title first, then student/intern only in the text, then the rest;
    within each: company sites before job boards, newest first."""
    keyword = job.get("matched_keyword")
    if keyword in DAILY_KEYWORDS:
        group = 0 if matching_keyword(job.get("title"), "", [keyword]) else 1
    else:
        group = 2
    return (
        group,
        1 if (job.get("source") or "").startswith(BOARD_SOURCES) else 0,
        -_posted_ordinal(job),  # newest first; no date = last
    )


def _posted_ordinal(job: dict) -> int:
    try:
        return date.fromisoformat(job.get("posted_at") or "").toordinal()
    except ValueError:
        return 0


def take_todays_share(backlog: list[dict], inbox_jobs: list[dict], limit: int = DAILY_LIMIT) -> tuple[list[dict], list[dict]]:
    """(today's jobs, the rest) - the backlog and today's inbox together, best first, each job once."""
    jobs = list({job["id"]: job for job in backlog + inbox_jobs}.values())
    jobs.sort(key=priority)
    return jobs[:limit], jobs[limit:]


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
    plan_cmd.add_argument("--limit", type=int, default=DAILY_LIMIT, help="most jobs the brain reads this morning")
    args = parser.parse_args(argv)

    backlog_path = args.state / "inbox" / "backlog.json"
    todays, rest = take_todays_share(_read_json(backlog_path, []), Inbox(args.state / "inbox").read(args.today), args.limit)
    _write_json(backlog_path, rest)
    plan = build_plan(load_board(args.board_dir), todays, args.today)
    plan["backlog"] = len(rest)
    out = args.state / "plan" / f"{args.today.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
