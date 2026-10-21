"""Run all company agents - step 1 of the morning run (stage 8, docs/agents/company-agents.md).

    python -m jobhunter.agents run [--today YYYY-MM-DD] [--weekly] [--state state] [--config config/sources.json]

--today defaults to the computer's local date (Israel), so the morning run needs no date command.
On Sundays the wider weekly keywords are used without --weekly.

For every company in the config: fetch its jobs in Israel that match the keywords (daily, or the wider
weekly words), then hand them over with collect_new - new jobs go to state/inbox/<date>.json.
Each company has its own memory, state/seen/<system>-<slug>.json, so one failing site never touches the others:
a company that fails is skipped, nothing of it is marked as seen, and the error goes to the report.

The report is saved to state/runs/<date>-agents.json (and printed) for the morning run's notification.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from jobhunter.agents import (amazon, apple, ashby, comeet, drushim, eightfold, google, greenhouse, hibob, hiremetech, jobmaster,
                              lever, oracle, sitemap, smartrecruiters, workday)
from jobhunter.state import Inbox, SeenStore, collect_new

AGENTS = {"greenhouse": greenhouse.fetch, "lever": lever.fetch, "workday": workday.fetch, "eightfold": eightfold.fetch,
          "comeet": comeet.fetch, "hiremetech": hiremetech.fetch, "amazon": amazon.fetch,
          "smartrecruiters": smartrecruiters.fetch, "oracle": oracle.fetch,
          "ashby": ashby.fetch, "apple": apple.fetch,
          "google": google.fetch, "hibob": hibob.fetch,
          "drushim": drushim.fetch, "jobmaster": jobmaster.fetch, "sitemap": sitemap.fetch}
SUNDAY = 6  # date.weekday()
CACHED = {"workday", "eightfold", "hiremetech", "smartrecruiters", "oracle", "apple", "jobmaster", "sitemap"}  # its job list has no text; each text is fetched once and kept in state/cache/<system>-<slug>/


def previous_report(runs_dir: Path, today: date) -> dict | None:
    """The latest report from before today (to notice a company that suddenly dropped to 0)."""
    earlier = sorted(p for p in runs_dir.glob("*-agents.json") if p.name[:10] < today.isoformat())
    return json.loads(earlier[-1].read_text(encoding="utf-8")) if earlier else None


def run_all(config: dict, state: Path, today: date, weekly: bool = False) -> dict:
    keywords = config["keywords"]["weekly" if weekly else "daily"]
    inbox = Inbox(state / "inbox")
    before = previous_report(state / "runs", today)
    before_by_source = {c["source"]: c for c in (before or {}).get("companies", [])}

    companies = []
    for system, entries in config["systems"].items():
        for company in entries:
            source = f"{system}:{company['slug']}"
            row = {"source": source, "company": company["company"]}
            try:
                fetch = AGENTS[system]
                extra = {"cache_dir": state / "cache" / f"{system}-{company['slug']}"} if system in CACHED else {}
                jobs, stats = fetch(company, config["israel"], keywords, **extra)
            except Exception as e:  # any failure of one site: skip it, mark nothing as seen
                row["error"] = f"{type(e).__name__}: {e}"
                companies.append(row)
                continue
            seen = SeenStore(state / "seen" / f"{system}-{company['slug']}.json")
            row.update(stats)
            row["new_titles"] = [j["title"] for j in jobs if seen.is_new(j["id"])]
            row["new"] = collect_new(jobs, seen, inbox, today)
            if stats["israel"] == 0 and (before_by_source.get(source) or {}).get("israel"):
                row["warning"] = f"0 jobs in Israel today, {before_by_source[source]['israel']} last run - the site may have changed"
            companies.append(row)

    return {
        "date": today.isoformat(),
        "kind": "weekly" if weekly else "daily",
        "new": sum(c.get("new", 0) for c in companies),
        "errors": [f"{c['company']}: {c['error']}" for c in companies if "error" in c],
        "warnings": [f"{c['company']}: {c['warning']}" for c in companies if "warning" in c],
        "companies": companies,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobhunter.agents")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--today", type=date.fromisoformat, default=date.today())
    run_cmd.add_argument("--weekly", action="store_true", help="wider keywords (safety net, once a week)")
    run_cmd.add_argument("--state", type=Path, default=Path("state"))
    run_cmd.add_argument("--config", type=Path, default=Path("config/sources.json"))
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    weekly = args.weekly or args.today.weekday() == SUNDAY  # the weekly safety net runs by itself on Sundays
    report = run_all(config, args.state, args.today, weekly)
    out = args.state / "runs" / f"{args.today.isoformat()}-agents.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
