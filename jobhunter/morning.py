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

# A job is "closed" when a weekly scan read its company after it was last seen and did not list it (find_closures).
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


def weekly_scans(state: Path) -> dict[str, str]:
    """source -> the date of its latest weekly scan that read it successfully (state/runs/*-agents.json)."""
    out: dict[str, str] = {}
    for path in sorted((state / "runs").glob("*-agents.json")):
        report = _read_json(path, {})
        if report.get("kind") != "weekly":
            continue
        for c in report.get("companies", []):
            if "error" not in c and "warning" not in c:
                out[c["source"]] = report.get("date") or path.name[:10]
    return out


def weekly_due(state: Path, today: date) -> bool:
    """Sundays, or any morning when the last weekly scan is more than a week old (a Sunday the computer was off)."""
    if today.weekday() == 6:
        return True
    dates = [path.name[:10] for path in (state / "runs").glob("*-agents.json") if _read_json(path, {}).get("kind") == "weekly"]
    return not dates or (today - date.fromisoformat(max(dates))).days > 7


def find_closures(board: dict[str, dict], state: Path, today: date) -> list[dict]:
    """Board jobs whose job is gone from the company site, and board jobs whose application deadline has passed.

    Gone = a weekly scan read the company successfully AFTER the job was last seen, and did not list it. The weekly
    words include the daily ones, so an open job always shows up in a weekly scan. (Until 21/10/2026 the rule was
    "not seen for 7 days", which closed 24 open jobs found by the weekly words when a Sunday scan was missed.)"""
    by_deadline = deadline_closures(board, today)
    done = {c["board_id"] for c in by_deadline}
    scanned = weekly_scans(state)
    seen_cache: dict[str, dict] = {}
    out = []
    for board_id, job in board.items():
        agent_id, source = job.get("agent_id"), job.get("source") or ""
        if board_id in done or not agent_id or job.get("status") not in CLOSABLE or source not in scanned or source.startswith(NO_FULL_LISTING):
            continue
        if source not in seen_cache:
            seen_cache[source] = _read_json(state / "seen" / f"{source.replace(':', '-')}.json", {})
        last = seen_cache[source].get(agent_id)
        if last and last >= scanned[source]:
            continue
        note = f"ירדה מאתר החברה (נראתה לאחרונה {last}, לא הופיעה בסריקה השבועית של {scanned[source]})" if last else "ירדה מאתר החברה"
        out.append({"board_id": board_id, "update": _closed(job, today, note)})
    return by_deadline + out


REMOVE_CLOSED_AFTER_DAYS = 7  # user's rule, 21/10/2026: a job closed for over a week leaves the board


def removals(board: dict[str, dict], today: date) -> list[str]:
    """Board jobs that have been "closed" for more than REMOVE_CLOSED_AFTER_DAYS -> deleted from the board.
    Only "closed" (gone from the site, or deadline passed); applied jobs never close, so they always stay.
    A deleted job does not come back as new: it is no longer listed on its site, and its id stays in the agent's
    memory (state/seen) for 30 more days."""
    out = []
    for board_id, job in board.items():
        if job.get("status") != "closed":
            continue
        closed_at = max((h.get("at") or "" for h in job.get("history") or [] if h.get("status") == "closed"), default="")
        try:
            days = (today - date.fromisoformat(closed_at[:10])).days
        except ValueError:
            continue
        if days > REMOVE_CLOSED_AFTER_DAYS:
            out.append(board_id)
    return out


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
    removed = set(removals(board, today))
    compactions = [
        {"board_id": board_id, "update": update}
        for board_id, job in board.items()
        if board_id not in removed and (update := compaction_update(job, today)) is not None
    ]
    return {"date": today.isoformat(), "jobs": planned, "compactions": compactions, "removals": sorted(removed)}


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
    for board_id in plan.get("removals", []):
        writes.append({"op": "delete", "collection": "jobs", "doc_id": board_id, "data": None,
                       "why": "נסגרה לפני יותר משבוע — יוצאת מהלוח"})
    return brain, writes, counts


def done_marker(state: Path, day: str) -> Path:
    """The morning's run row, written by apply_brain when the cards are on the board (state/board/runs/<day>.json).
    The older place (state/plan/done/runs) still counts for mornings marked before 24/10/2026."""
    new = state / "board" / "runs" / f"{day}.json"
    old = state / "plan" / "done" / "runs" / f"{day}.json"
    return old if old.exists() and not new.exists() else new


def unfinished_jobs(state: Path) -> list[dict]:
    """The last prepared morning's jobs, if the Claude run never finished it (computer off, app closed, a stall).
    They go back to the queue, so a missed morning loses nothing (21/10/2026)."""
    last = state / "plan" / "last-prepare.txt"
    if not last.exists():
        return []
    day = last.read_text(encoding="utf-8").strip()
    if done_marker(state, day).exists() or (state / "plan" / "applied" / f"{day}.txt").exists():
        return []
    return [item["inbox_job"] for item in _read_json(state / "plan" / f"{day}.json", {}).get("jobs", [])]


def prepare(state: Path, board_dir: Path, today: date, limit: int = DAILY_LIMIT,
            config: Path = Path("config/sources.json"), run_agents: bool = True, use_marks: bool = True) -> dict:
    """Steps 1-3 of the morning run in one command: sub-agents, code prefilter, plan, and the brain's files."""
    from jobhunter import prefilter
    from jobhunter.agents.__main__ import SUNDAY, run_all

    plan_dir = state / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    report_path = state / "runs" / f"{today.isoformat()}-agents.json"
    if run_agents:
        report = run_all(json.loads(config.read_text(encoding="utf-8")), state, today, weekly_due(state, today))
        _write_json(report_path, report)
    report = _read_json(report_path, {"new": 0, "errors": [], "warnings": [], "companies": [], "kind": "daily"})

    backlog_path = state / "inbox" / "backlog.json"
    requeued = unfinished_jobs(state)
    candidates = list({j["id"]: j for j in requeued + _read_json(backlog_path, []) + Inbox(state / "inbox").read(today)}.values())
    on_board = {p.stem for p in (board_dir / "jobs").glob("*.json")}
    candidates = [j for j in candidates if doc_id(j["id"]) not in on_board]  # done by an earlier attempt today
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
    from jobhunter import store
    applied = store.apply_writes(board_dir, writes)  # the code writes the board itself (6/11/2026)
    files = {name: plan_dir / f"{today.isoformat()}-{name}.json" for name in ("brain", "cards", "run")}
    _write_json(files["brain"], brain)
    files["cards"].unlink(missing_ok=True)

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
        "removed": len(plan["removals"]),
        "backlog": len(rest),
        "errors": report.get("errors", []),
        "warnings": report.get("warnings", []) + ([marks_error] if marks_error else []),
    }
    _write_json(files["run"], run)
    (plan_dir / "last-prepare.txt").write_text(today.isoformat(), encoding="utf-8")
    done_marker(state, today.isoformat()).unlink(missing_ok=True)
    result = {
        "date": today.isoformat(),
        "sources_read": f"{run['sources_read']}/{run['sources_total']}",
        "found_new": run["found_new"],
        "errors": run["errors"],
        "warnings": run["warnings"],
        "prefiltered": len(filtered),
        "to_brain": len(brain),
        "borderline_jobs": sum(1 for b in brain if b["borderline"]),
        "code_writes": applied,
        "backlog": len(rest),
        "requeued": len(requeued),
        "files": {name: str(path.resolve()) for name, path in files.items()},
    }
    _write_json(plan_dir / "next.json", result)  # what the brain reads first (docs/agents/brain-run.md)
    return result


def claude_exe() -> str | None:
    """The Claude Code command line: CLAUDE_EXE, `claude` on PATH, or the newest one the Claude app ships."""
    import os
    import shutil
    if os.environ.get("CLAUDE_EXE"):
        return os.environ["CLAUDE_EXE"]
    if found := shutil.which("claude"):
        return found
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude-Data"
    exes = sorted(base.glob("claude_*/claude-code/*/*/claude.exe"), key=lambda p: [int(x) if x.isdigit() else x for x in p.parts[-3].split(".")])
    return str(exes[-1]) if exes else None


BRAIN_PROMPT = ("You are the JobHunter brain. Read docs/agents/brain-run.md and follow it exactly, from start to end. "
                "Use only Read, Glob, Grep and Write. Nobody is watching: do not ask questions.")


def notify(title: str, text: str) -> bool:
    """A Windows toast. The Windows task runs in the user's own session, so it shows on their screen. Never raises:
    a notification that fails must not break the morning (6-10/11/2026: weeks went by without anyone noticing)."""
    import html
    import os
    import subprocess
    script = (
        "$ErrorActionPreference='Stop';"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        "$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text>' + $env:JH_TITLE + '</text><text>' + $env:JH_TEXT + '</text></binding></visual></toast>');"
        "$n = New-Object Windows.UI.Notifications.ToastNotification $x;"
        r"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe').Show($n)")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=30,
                              env={**os.environ, "JH_TITLE": html.escape(title), "JH_TEXT": html.escape(text)})
        return done.returncode == 0
    except Exception:
        return False


def notify_once(state: Path, key: str, title: str, text: str) -> None:
    """notify(), once per key (a key carries the day), so an hourly retry does not repeat the message."""
    marker = state / "plan" / "notified" / f"{key}.txt"
    if marker.exists():
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(text, encoding="utf-8")
    notify(title, text)


def run_brain(state: Path, timeout_minutes: int = 90) -> dict:
    """Claude Code headless (`claude -p`) on the Pro subscription: reads the brain file, writes the cards file.
    Headless mode never waits for an approval - a tool it may not use is refused and the run goes on."""
    import subprocess
    nxt = _read_json(state / "plan" / "next.json", {})
    day = nxt.get("date")

    def finish(result: dict) -> dict:
        _write_json(state / "plan" / f"{day}-brain-status.json", result)
        return result

    if not nxt.get("to_brain"):
        return {"date": day, "brain": "nothing to read"}
    exe = claude_exe()
    if not exe:
        return finish({"date": day, "brain": "error", "report": "Claude Code command line not found"})
    try:
        done = subprocess.run([exe, "-p", BRAIN_PROMPT, "--permission-mode", "acceptEdits",
                               "--allowedTools", "Read", "Glob", "Grep", "Write", "--output-format", "text"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_minutes * 60)
    except subprocess.TimeoutExpired:
        return finish({"date": day, "brain": "error", "report": f"no answer in {timeout_minutes} minutes"})
    out = (done.stdout + done.stderr).strip()
    return finish({"date": day, "brain": "ok" if done.returncode == 0 else f"error {done.returncode}", "report": out[-3000:]})


def apply_brain(state: Path, board_dir: Path) -> dict:
    """The cards onto the board, the run row (state/board/runs/<date>.json - also the "done" marker), and any job
    the brain left without a card back to the queue."""
    from jobhunter import store
    nxt = _read_json(state / "plan" / "next.json", {})
    day = nxt.get("date")
    if not day:
        return {"apply": "nothing prepared"}
    plan_dir = state / "plan"
    brain = _read_json(plan_dir / f"{day}-brain.json", [])
    cards = store.read_cards(plan_dir / f"{day}-cards.json")
    if brain and not cards:
        # visible on the site's report: the morning's jobs wait in the queue until Claude can read them
        run = _read_json(plan_dir / f"{day}-run.json", {})
        brain_report = _read_json(plan_dir / f"{day}-brain-status.json", {})
        run["brain_error"] = brain_report.get("report") or "Claude לא כתב כרטיסים"
        _write_json(plan_dir / f"{day}-run.json", run)
        reason = run["brain_error"]
        hint = "Claude לא מחובר. הרץ: claude auth login" if "Not logged in" in reason else reason[:120]
        notify_once(state, f"brain-{day}", "JobHunter: Claude לא קרא את המשרות", f"{hint}. המשרות מחכות בתור, ולא אבדה אף אחת.")
        return {"date": day, "apply": "no cards file - the jobs stay for the next run", "brain_error": run["brain_error"][-300:]}
    counts, missing = store.apply_cards(board_dir, brain, cards, day)
    if missing:
        backlog_path = state / "inbox" / "backlog.json"
        plan = _read_json(plan_dir / f"{day}.json", {})
        by_doc = {doc_id(item["inbox_job"]["id"]): item["inbox_job"] for item in plan.get("jobs", [])}
        _write_json(backlog_path, [by_doc[m["doc_id"]] for m in missing if m["doc_id"] in by_doc] + _read_json(backlog_path, []))
    run = _read_json(plan_dir / f"{day}-run.json", {})
    run.update({k: counts[k] for k in ("passed", "brain_filtered", "far", "borderline")})
    run["summary"] = (f"{counts['passed']} עברו · {counts['brain_filtered']} סוננו ע\"י המוח · {run.get('prefiltered_count', 0)} סוננו בקוד"
                      f" · {counts['merged'] + run.get('duplicates_code', 0)} כפילויות · {run.get('backlog', 0)} ממתינות")
    (plan_dir / "applied").mkdir(parents=True, exist_ok=True)
    (plan_dir / "applied" / f"{day}.txt").write_text("1", encoding="utf-8")  # the cards are on the board: never requeue them
    result = {"date": day, "apply": "ok", **{k: v for k, v in counts.items() if k != "borderline"}, "back_to_queue": len(missing)}
    read, total = run.get("sources_read", 0), run.get("sources_total", 0)
    if total and read * 2 < total:
        # most sites could not be read (no network after a wake-up, say): the day is NOT done, a later attempt follows
        result["apply"] = f"ok, but only {read}/{total} sources were read - another attempt will follow"
        return result
    _write_json(done_marker(state, day), run)
    return result


def online(timeout: float = 5.0) -> bool:
    """Is the network up? (Right after a wake-up it often is not yet.)"""
    import socket
    for host in ("github.com", "1.1.1.1"):
        try:
            socket.create_connection((host, 443), timeout=timeout).close()
            return True
        except OSError:
            continue
    return False


def due(state: Path, today: date, check_network: bool = False) -> tuple[bool, str]:
    """Should the hourly Windows task run the morning now? Not when today's morning is already on the board, and not
    while another run is going (a lock younger than 3 hours). The task tries every hour from 08:00, because Windows'
    "run a missed task when available" did not catch up after sleep (9/11/2026)."""
    import time
    if done_marker(state, today.isoformat()).exists():
        return False, "today's morning is already done"
    lock = state / "plan" / "running.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < 3 * 3600:
        return False, "another run is going"
    attempts = state / "plan" / f"attempts-{today.isoformat()}.txt"
    if attempts.exists() and int(attempts.read_text() or 0) >= MAX_ATTEMPTS:
        notify_once(state, f"attempts-{today.isoformat()}", "JobHunter: הריצה נכשלה היום",
                    f"אחרי {MAX_ATTEMPTS} ניסיונות הבוקר לא הושלם. הפרטים בתיקיית state/logs. המשרות מחכות בתור.")
        return False, f"{MAX_ATTEMPTS} attempts today already - see the morning log"
    if check_network and not online():
        return False, "no network yet"  # does not use an attempt: the next trigger tries again
    return True, "run"


MAX_ATTEMPTS = 5  # a run that keeps failing (e.g. Claude signed out) must not read every site every hour


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
    code, out = _git("add", str(state / "seen"), str(state / "inbox"), str(board_dir))
    if code == 0:
        message = f"Morning run {today.isoformat()}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        code, out = _git("commit", "-m", message)
        if code != 0 and ("nothing to commit" in out or "no changes added to commit" in out):
            code, out = 0, "nothing to commit"
    if code == 0 and push:
        code, out = _git("push")
    result["git"] = "ok" if code == 0 else f"error: {out[-400:]}"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunter.morning")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "prepare", "finish", "brain", "apply", "due", "lock", "unlock"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--board-dir", type=Path, default=Path("state/board"), required=(name == "plan"))
        cmd.add_argument("--today", type=date.fromisoformat, default=date.today())
        cmd.add_argument("--state", type=Path, default=Path("state"))
        cmd.add_argument("--limit", type=int, default=DAILY_LIMIT, help="most jobs the brain reads this morning")
        cmd.add_argument("--no-agents", action="store_true", help="prepare: reuse today's agents report (a re-run)")
        cmd.add_argument("--no-push", action="store_true", help="finish: commit without pushing")
        cmd.add_argument("--wait", action="store_true", help="finish: first wait for the Claude run's done marker")
        cmd.add_argument("--if-done", action="store_true",
                         help="finish: only if the Claude run is done and this morning was not published yet (hourly)")
        cmd.add_argument("--wait-hours", type=float, default=10.0)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "prepare":
        result = prepare(args.state, args.board_dir, args.today, args.limit, run_agents=not args.no_agents)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "due":
        run, why = due(args.state, args.today, check_network=True)
        print(why)
        return 0 if run else 1
    if args.cmd == "lock":
        (args.state / "plan").mkdir(parents=True, exist_ok=True)
        (args.state / "plan" / "running.lock").write_text(args.today.isoformat(), encoding="utf-8")
        attempts = args.state / "plan" / f"attempts-{args.today.isoformat()}.txt"
        attempts.write_text(str(int(attempts.read_text() or 0) + 1 if attempts.exists() else 1), encoding="utf-8")
        return 0
    if args.cmd == "unlock":
        (args.state / "plan" / "running.lock").unlink(missing_ok=True)
        return 0
    if args.cmd == "brain":
        print(json.dumps(run_brain(args.state), ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "apply":
        print(json.dumps(apply_brain(args.state, args.board_dir), ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "finish":
        # the morning that prepare prepared - a run that waited past midnight still finishes its own date (15/10/2026)
        last = args.state / "plan" / "last-prepare.txt"
        day = args.today if "--today" in (argv or sys.argv) or not last.exists() else date.fromisoformat(last.read_text().strip())
        published = args.state / "plan" / "published" / f"{day.isoformat()}.txt"
        if args.if_done and (published.exists() or not done_marker(args.state, day.isoformat()).exists()):
            print(json.dumps({"date": day.isoformat(), "skipped": "already published" if published.exists() else "Claude not done yet"}))
            return 0
        if args.wait:  # Windows Task Scheduler: prepare, then this waits for the Claude run, then publishes (21/10/2026)
            import time
            deadline = time.monotonic() + args.wait_hours * 3600
            while not done_marker(args.state, day.isoformat()).exists() and time.monotonic() < deadline:
                time.sleep(60)
            print(json.dumps({"waited_for": day.isoformat(), "claude_done": done_marker(args.state, day.isoformat()).exists()}))
        result = finish(args.state, args.board_dir, day, push=not args.no_push)
        if done_marker(args.state, day.isoformat()).exists():  # this morning's board is in the page: no more publishing needed
            published.parent.mkdir(parents=True, exist_ok=True)
            published.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=1))
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
