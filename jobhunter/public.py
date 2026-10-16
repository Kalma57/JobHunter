"""The public site (docs/public-page.md): the job board on GitHub Pages, for the user and for anyone with the link.

    python -m jobhunter.public build [--board-dir state/board] [--state state]   (also runs inside `morning finish`)

Built from the board snapshot taken after the morning writes: the template site/public.html + the data as JSON
-> public/index.html. Everyone sees the whole board (user's decision, 16/10/2026: statuses and notes visible);
only the owner can change it - the page writes the owner's marks to statuses.json on the board-data branch with
the owner's own GitHub key (jobhunter/overlay.py). The embedded marks are this morning's; the page fetches the
latest ones when it opens.
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
HEAVY = ("applied_description",)  # a copy of the description, kept on the board for the user's records


def board_jobs(board: dict[str, dict]) -> list[dict]:
    """Every board job (the page has tabs for every status), with its board id."""
    return [{"id": doc_id, **{k: v for k, v in job.items() if k not in HEAVY}} for doc_id, job in sorted(board.items())]


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
        "errors": report.get("errors", []),
        "warnings": report.get("warnings", []),
        "prefiltered_list": run.get("prefiltered", []),
    }


def build(board_dir: Path, state: Path, today: date, out_dir: Path = OUT_DIR) -> dict:
    from jobhunter.morning import load_board
    from jobhunter import overlay
    marks, _ = overlay.load()
    data = {"config": _read_json(CONFIG, {}), "run": run_numbers(state, today), "jobs": board_jobs(load_board(board_dir)),
            "marks": marks}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return {"path": str((out_dir / "index.html").resolve()), "jobs": len(data["jobs"]), "sources_read": data["run"]["sources_read"]}


def publish(today: date, out_dir: Path = OUT_DIR) -> str:
    """Publish public/ as the gh-pages branch of the project repo (GitHub Pages: kalma57.github.io/JobHunter/).

    public/ is its own small git history (only index.html), so gh-pages never carries the project's files.
    It is committed there, fetched into the project repo and pushed through the project's own origin.
    Returns "ok", "unchanged", or "error: ..."; without the public/ history, "not set up".
    """
    import subprocess

    if not (out_dir / ".git").exists():
        return "not set up"

    def git(*args: str) -> tuple[int, str]:
        done = subprocess.run(["git", "-C", str(out_dir), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return done.returncode, (done.stdout + done.stderr).strip()

    git("add", "-A")
    code, out = git("commit", "-m", f"Morning run {today.isoformat()}")
    if code != 0 and "nothing to commit" not in out:
        return f"error: {out[-300:]}"
    for args in (["fetch", "-q", str(out_dir), "gh-pages"], ["push", "-q", "origin", "FETCH_HEAD:refs/heads/gh-pages"]):
        done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if done.returncode != 0:
            return f"error: {(done.stdout + done.stderr).strip()[-300:]}"
    return "ok"


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
