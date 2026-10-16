"""The code half of the morning orchestrator run (stage 6).

    python -m jobhunter.morning prepare   everything before the brain in one command (docs/agents/morning-run.md)
    python -m jobhunter.morning finish    everything after the board writes: public page + state backup to git
    python -m jobhunter.morning plan --board-dir <dir> --today YYYY-MM-DD   (the plan step alone)

<dir> holds a snapshot of the board's jobs (one <id>.json per job, as ArtifactData saves them with
out_dir, under <dir>/jobs/). The plan is printed and saved to state/plan/<date>.json:

  jobs         today's share of the inbox (at most DAILY_LIMIT), each with its duplicate candidates on the
               board (or earlier in today's share)
  backlog      how many jobs wait for the next mornings
  closures     board jobs whose job left the company site -> status "closed"
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

# A job is "closed" when its company was read successfully today but the job hasn't been listed for more than
# CLOSED_AFTER_DAYS (a week, so jobs found only by the Sunday scan aren't closed between Sundays).
CLOSED_AFTER_DAYS = 7
CLOSABLE = {"new", "filtered", "hold", "not_interested"}  # applied & co. keep their status; the user tracks them
NO_FULL_LISTING = ("hiremetech:", "jobmaster:")  # read only the newest pages, so an old job not listed there is not a sign

DAILY_LIMIT = 40
DAILY_KEYWORDS = {"Student", "Intern", "Internship", "סטודנט"}
BOARD_SOURCES = ("hiremetech:", "drushim:", "jobmaster:")  # job boards: often card details only, and many repeat company-site jobs


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


def _closed(job: dict, today: date, note: str) -> dict:
    return {"status": "closed",
            "history": list(job.get("history") or []) + [{"status": "closed", "at": f"{today.isoformat()}T07:00:00Z", "note": note}]}


def deadline_closures(board: dict[str, dict], today: date) -> list[dict]:
    """Board jobs whose application deadline has passed. Only applied & co. stay (user's rule, 16/10/2026:
    a job you can no longer apply to is interesting only if you already applied)."""
    out = []
    for board_id, job in board.items():
        deadline = job.get("deadline")
        if job.get("status") not in CLOSABLE or not deadline:
            continue
        try:
            passed = date.fromisoformat(str(deadline)[:10]) < today
        except ValueError:
            continue
        if passed:
            out.append({"board_id": board_id, "update": _closed(job, today, f"מועד ההגשה עבר ({str(deadline)[:10]})")})
    return out


def find_closures(board: dict[str, dict], state: Path, today: date) -> list[dict]:
    """Board jobs from a company agent whose job is gone from the site (see CLOSED_AFTER_DAYS), and board jobs
    whose application deadline has passed."""
    by_deadline = deadline_closures(board, today)
    done = {c["board_id"] for c in by_deadline}
    report = _read_json(state / "runs" / f"{today.isoformat()}-agents.json", {})
    # a site that failed, or suddenly listed 0 jobs (a glitch, not 0 jobs), says nothing about which jobs closed
    read_ok = {c["source"] for c in report.get("companies", []) if "error" not in c and "warning" not in c}
    seen_cache: dict[str, dict] = {}
    out = []
    for board_id, job in board.items():
        agent_id, source = job.get("agent_id"), job.get("source") or ""
        if board_id in done or not agent_id or job.get("status") not in CLOSABLE or source not in read_ok or source.startswith(NO_FULL_LISTING):
            continue
        if source not in seen_cache:
            seen_cache[source] = _read_json(state / "seen" / f"{source.replace(':', '-')}.json", {})
        last = seen_cache[source].get(agent_id)
        if last and (today - date.fromisoformat(last)).days <= CLOSED_AFTER_DAYS:
            continue
        note = f"ירדה מאתר החברה (נראתה לאחרונה {last})" if last else "ירדה מאתר החברה"
        out.append({"board_id": board_id, "update": _closed(job, today, note)})
    return by_deadline + out


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


def doc_id(job_id: str) -> str:
    """The board document id of a sub-agent job ("amazon:10478260" -> "amazon-10478260")."""
    return job_id.replace(":", "-")


def _sighting(job: dict, today: date) -> dict:
    return {"source": job.get("source"), "url": job.get("url"), "date": today.isoformat()}


def _short(job: dict) -> dict:
    return {k: job.get(k) for k in ("title", "company", "location", "url", "source")}


def split_plan(plan: dict, board: dict[str, dict], today: date) -> tuple[list[dict], list[dict], dict]:
    """What the code settles for sure, and what only the brain can. Returns (brain jobs, writes, counts):

      exact match on the board   -> a write: the board job gets one more sighting (its status is untouched);
                                    a company-site job takes over url / apply_url from a job-board job
      exact match earlier today  -> the first one carries the second as a sighting
      everything else            -> a brain job, with its borderline candidates (short) for the brain to judge
    Closures and compactions become writes too.
    """
    brain: list[dict] = []
    by_inbox_id: dict[str, dict] = {}
    writes: list[dict] = []
    counts = {"exact_board": 0, "exact_today": 0}
    for item in plan["jobs"]:
        job, matches = item["inbox_job"], item["matches"]
        exact = [m for m in matches if m["kind"] == "exact"]
        on_board = [m for m in exact if not m["board_id"].startswith("inbox:")]
        if on_board:
            board_id = on_board[0]["board_id"]
            other = board.get(board_id, {})
            earlier = next((w for w in writes if w["doc_id"] == board_id), None)
            if earlier:  # a second job matching the same board job this morning: one write per document
                earlier["data"]["sightings"].append(_sighting(job, today))
                counts["exact_board"] += 1
                continue
            update = {"sightings": list(other.get("sightings") or []) + [_sighting(job, today)]}
            if not (job.get("source") or "").startswith(BOARD_SOURCES) and (other.get("source") or "").startswith(BOARD_SOURCES):
                update.update({"url": job.get("url"), "apply_url": job.get("apply_url") or job.get("url")})
            writes.append({"op": "update", "collection": "jobs", "doc_id": board_id, "data": update,
                           "why": f"{on_board[0]['reason']}: {job.get('title')}"})
            counts["exact_board"] += 1
            continue
        first = by_inbox_id.get(exact[0]["board_id"].removeprefix("inbox:")) if exact else None
        if first:  # the same job twice this morning
            first["fields"]["sightings"].append(_sighting(job, today))
            counts["exact_today"] += 1
            continue
        borderline = []
        for m in matches:
            if m["kind"] != "borderline":
                continue
            other = board.get(m["board_id"]) or (by_inbox_id.get(m["board_id"].removeprefix("inbox:")) or {}).get("job") or {}
            borderline.append({**m, **_short(other)})
        entry = {
            "doc_id": doc_id(job["id"]),
            "fields": {"agent_id": job["id"], "source": job.get("source"), "first_seen": today.isoformat(), "notes": "",
                       "sightings": [_sighting(job, today)]},
            "history_note": f'נמצא ע"י {job.get("source")}',
            "job": {k: job.get(k) for k in ("title", "company", "location", "url", "apply_url", "posted_at", "job_number",
                                            "matched_keyword", "description")},
            "borderline": borderline,
        }
        by_inbox_id[job["id"]] = entry
        brain.append(entry)
    for item in plan.get("closures", []) + plan.get("compactions", []):
        writes.append({"op": "update", "collection": "jobs", "doc_id": item["board_id"], "data": item["update"],
                       "why": "נסגרה" if item["update"].get("status") == "closed" else "כלל 30 הימים"})
    return brain, writes, counts


def _write_batch_files(writes: list[dict], out_dir: Path) -> list[dict]:
    """Each write's data in its own file, so the board writes need no retyping. Returns the batch entries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    entries = []
    for n, w in enumerate(writes, 1):
        path = out_dir / f"{n:03d}-{w['doc_id']}.json"
        path.write_text(json.dumps(w["data"], ensure_ascii=False, indent=1), encoding="utf-8")
        entries.append({"op": w["op"], "collection": w["collection"], "doc_id": w["doc_id"],
                        "file_path": str(path.resolve()), "if_version": None, "why": w["why"]})
    return entries


def prepare(state: Path, board_dir: Path, today: date, limit: int = DAILY_LIMIT,
            config: Path = Path("config/sources.json"), run_agents: bool = True, use_marks: bool = True) -> dict:
    """Steps 1-3 of the morning run in one command: sub-agents, code prefilter, plan, and the brain's files."""
    from jobhunter import prefilter
    from jobhunter.agents.__main__ import SUNDAY, run_all

    plan_dir = state / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    report_path = state / "runs" / f"{today.isoformat()}-agents.json"
    if run_agents:
        report = run_all(json.loads(config.read_text(encoding="utf-8")), state, today, today.weekday() == SUNDAY)
        _write_json(report_path, report)
    report = _read_json(report_path, {"new": 0, "errors": [], "warnings": [], "companies": [], "kind": "daily"})

    backlog_path = state / "inbox" / "backlog.json"
    candidates = list({j["id"]: j for j in _read_json(backlog_path, []) + Inbox(state / "inbox").read(today)}.values())
    keep, filtered = prefilter.split(candidates, prefilter.load_rules())
    todays, rest = take_todays_share(keep, [], limit)
    _write_json(backlog_path, rest)

    from jobhunter import overlay
    marks, marks_error = overlay.load() if use_marks else ({}, None)
    board = overlay.apply(load_board(board_dir), marks)  # the user's marks from the public site count
    plan = build_plan(board, todays, today)
    plan["backlog"] = len(rest)
    plan["closures"] = find_closures(board, state, today)
    _write_json(plan_dir / f"{today.isoformat()}.json", plan)

    brain, writes, counts = split_plan(plan, board, today)
    files = {name: plan_dir / f"{today.isoformat()}-{name}.json" for name in ("brain", "batch", "run")}
    _write_json(files["brain"], brain)
    _write_json(files["batch"], _write_batch_files(writes, plan_dir / f"{today.isoformat()}-writes"))

    companies = report.get("companies", [])
    run = {
        "at": f"{today.isoformat()}T07:00:00Z",
        "kind": report.get("kind", "daily"),
        "sources_read": sum(1 for c in companies if "error" not in c),
        "sources_total": len(companies),
        "found_new": report.get("new", 0),
        "candidates": len(candidates),  # today's new jobs + yesterday's backlog
        "after_prefilter": len(keep),
        "prefiltered_count": len(filtered),
        "prefiltered": [{**_short(j), "reason": j["prefilter_reason"]} for j in filtered],
        "to_brain": len(brain),
        "duplicates_code": counts["exact_board"] + counts["exact_today"],
        "closed": len(plan["closures"]),
        "compacted": len(plan["compactions"]),
        "backlog": len(rest),
        "errors": report.get("errors", []),
        "warnings": report.get("warnings", []) + ([marks_error] if marks_error else []),
    }
    _write_json(files["run"], run)
    (plan_dir / "last-prepare.txt").write_text(today.isoformat(), encoding="utf-8")
    return {
        "date": today.isoformat(),
        "sources_read": f"{run['sources_read']}/{run['sources_total']}",
        "found_new": run["found_new"],
        "errors": run["errors"],
        "warnings": run["warnings"],
        "prefiltered": len(filtered),
        "to_brain": len(brain),
        "borderline_jobs": sum(1 for b in brain if b["borderline"]),
        "code_writes": len(writes),
        "backlog": len(rest),
        "files": {name: str(path.resolve()) for name, path in files.items()},
    }


def _git(*args: str) -> tuple[int, str]:
    import subprocess
    done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return done.returncode, (done.stdout + done.stderr).strip()


def finish(state: Path, board_dir: Path, today: date, push: bool = True) -> dict:
    """After the board writes: rebuild the public page from the fresh board snapshot, back up the state to git."""
    result: dict = {"date": today.isoformat()}
    try:
        from jobhunter import public
        result["public"] = public.build(board_dir, state, today)
        result["public"]["published"] = public.publish(today)
    except Exception as e:  # the backup must still happen
        result["public_error"] = f"{type(e).__name__}: {e}"
    code, out = _git("add", str(state / "seen"), str(state / "inbox"))
    if code == 0:
        message = f"Morning run {today.isoformat()}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        code, out = _git("commit", "-m", message)
        if code != 0 and "nothing to commit" in out:
            code, out = 0, "nothing to commit"
    if code == 0 and push:
        code, out = _git("push")
    result["git"] = "ok" if code == 0 else f"error: {out[-400:]}"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunter.morning")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "prepare", "finish"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--board-dir", type=Path, default=Path("state/board"), required=(name == "plan"))
        cmd.add_argument("--today", type=date.fromisoformat, default=date.today())
        cmd.add_argument("--state", type=Path, default=Path("state"))
        cmd.add_argument("--limit", type=int, default=DAILY_LIMIT, help="most jobs the brain reads this morning")
        cmd.add_argument("--no-agents", action="store_true", help="prepare: reuse today's agents report (a re-run)")
        cmd.add_argument("--no-push", action="store_true", help="finish: commit without pushing")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "prepare":
        result = prepare(args.state, args.board_dir, args.today, args.limit, run_agents=not args.no_agents)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "finish":
        # the morning that prepare prepared - a run that waited past midnight still finishes its own date (15/10/2026)
        last = args.state / "plan" / "last-prepare.txt"
        day = args.today if "--today" in (argv or sys.argv) or not last.exists() else date.fromisoformat(last.read_text().strip())
        print(json.dumps(finish(args.state, args.board_dir, day, push=not args.no_push), ensure_ascii=False, indent=1))
        return 0

    backlog_path = args.state / "inbox" / "backlog.json"
    todays, rest = take_todays_share(_read_json(backlog_path, []), Inbox(args.state / "inbox").read(args.today), args.limit)
    _write_json(backlog_path, rest)
    board = load_board(args.board_dir)
    plan = build_plan(board, todays, args.today)
    plan["backlog"] = len(rest)
    plan["closures"] = find_closures(board, args.state, args.today)
    out = args.state / "plan" / f"{args.today.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
