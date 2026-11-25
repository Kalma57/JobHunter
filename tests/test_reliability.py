"""Tests for the 25/11/2026 reliability work: a failing HireMeTech is an error (not "0 jobs"), and a source that failed
for a reason that may pass is read again later the same day."""

import json
import os
import time
from datetime import date

import pytest

from jobhunter.agents.__main__ import merge_reports, retryable_failures
from jobhunter.agents.hiremetech import collect
from jobhunter.agents.http import FetchError
from jobhunter.morning import MAX_RETRIES, apply_brain, done_marker, due, retry_due

TODAY = date(2026, 11, 25)
DAY = TODAY.isoformat()


# ---- HireMeTech: its own server failing must not look like "no jobs"

def test_an_empty_first_page_is_an_error_not_zero_jobs():
    with pytest.raises(FetchError):
        collect(lambda n: [], lambda job_id: "", {"slug": "juniors"}, ["Student"], None, TODAY, 5)


def test_an_empty_later_page_just_ends_the_list():
    pages = {1: [("101", "Software Student\n·\nTel Aviv")], 2: []}
    jobs, stats = collect(lambda n: pages.get(n, []), lambda job_id: "", {"slug": "juniors", "company": "HireMeTech", "host": "juniors.hiremetech.com"},
                          ["Student"], None, TODAY, 5)
    assert stats["pages"] == 2 and stats["israel"] == 1 and len(jobs) == 1


# ---- which failures are worth another try the same day

REPORT = {"companies": [
    {"source": "hiremetech:juniors", "company": "HireMeTech", "error": "FetchError: HireMeTech עצמו לא מחזיר משרות"},
    {"source": "workday:kla", "company": "KLA", "error": "bot check", "blocked": True},
    {"source": "eightfold:microsoft", "company": "Microsoft", "error": "FetchError: HTTP 429 from https://x"},
    {"source": "lever:mobileye", "company": "Mobileye", "israel": 150, "new": 2},
]}


def test_only_failures_that_may_pass_are_retried():
    assert retryable_failures(REPORT) == {"hiremetech:juniors"}  # not blocked sites, not a site that said 429


def test_a_retry_pass_replaces_only_the_retried_rows():
    fresh = {"companies": [{"source": "hiremetech:juniors", "company": "HireMeTech", "israel": 80, "new": 20}]}
    merged = merge_reports(REPORT, fresh)
    by = {c["source"]: c for c in merged["companies"]}
    assert "error" not in by["hiremetech:juniors"] and by["workday:kla"]["blocked"]
    assert merged["new"] == 22 and len(merged["errors"]) == 2  # Mobileye 2 + HireMeTech 20; KLA and Microsoft still failed


# ---- when due() allows a second look

def _state(tmp_path, report=REPORT, done=True):
    (tmp_path / "runs").mkdir(parents=True)
    (tmp_path / "plan").mkdir()
    (tmp_path / "runs" / f"{DAY}-agents.json").write_text(json.dumps(report), encoding="utf-8")
    if done:
        marker = done_marker(tmp_path, DAY)
        marker.parent.mkdir(parents=True)
        marker.write_text("{}", encoding="utf-8")
    last = tmp_path / "plan" / "last-prepare.txt"
    last.write_text(DAY, encoding="utf-8")
    old = time.time() - 2 * 3600
    os.utime(last, (old, old))  # the last run was two hours ago
    return tmp_path


def test_a_finished_day_with_a_flapping_source_is_read_again(tmp_path):
    state = _state(tmp_path)
    assert retry_due(state, TODAY)
    assert due(state, TODAY) == (True, "retry the sources that failed")


def test_no_second_look_right_after_a_run_or_after_three_retries_or_when_all_is_well(tmp_path):
    state = _state(tmp_path)
    os.utime(state / "plan" / "last-prepare.txt", None)  # just now
    assert not retry_due(state, TODAY) and due(state, TODAY) == (False, "today's morning is already done")
    old = time.time() - 2 * 3600
    os.utime(state / "plan" / "last-prepare.txt", (old, old))
    (state / "plan" / f"retries-{DAY}.txt").write_text(str(MAX_RETRIES), encoding="utf-8")
    assert not retry_due(state, TODAY)
    (state / "plan" / f"retries-{DAY}.txt").unlink()
    (state / "runs" / f"{DAY}-agents.json").write_text(json.dumps({"companies": [{"source": "a:b", "company": "A", "israel": 3}]}), encoding="utf-8")
    assert not retry_due(state, TODAY)


# ---- a retry pass adds to the morning's numbers instead of replacing them

def test_apply_adds_to_the_morning_totals(tmp_path):
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "next.json").write_text(json.dumps({"date": DAY}), encoding="utf-8")
    (plan / f"{DAY}-brain.json").write_text("[]", encoding="utf-8")
    (plan / f"{DAY}-run.json").write_text(json.dumps({"sources_read": 38, "sources_total": 39, "passed": 2, "brain_filtered": 5,
                                                      "far": 1, "borderline": ["x"], "prefiltered_count": 4}), encoding="utf-8")
    (tmp_path / "board" / "jobs").mkdir(parents=True)
    apply_brain(tmp_path, tmp_path / "board")
    run = json.loads(done_marker(tmp_path, DAY).read_text(encoding="utf-8"))
    assert run["passed"] == 2 and run["brain_filtered"] == 5 and run["borderline"] == ["x"]  # an empty pass changes nothing
    assert "2 עברו" in run["summary"]
