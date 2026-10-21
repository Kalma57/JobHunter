"""Tests for the one-command morning run (14/10/2026): code prefilter, dedup levels, prepare's split, the job-board
agents (Drushim, JobMaster) and the public page. No network: saved site responses in tests/fixtures."""

import json
from datetime import date
from pathlib import Path

from jobhunter.dedup import find_matches
from jobhunter.morning import split_plan, build_plan
from jobhunter.prefilter import load_rules, reject_reason, years_asked

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 14)
RULES = load_rules()


def _job(title, description="", **kw):
    return {"id": kw.pop("id", "x:1"), "title": title, "description": description, **kw}


# ---- prefilter ----

def test_prefilter_keeps_student_jobs_even_with_years_in_the_text():
    job = _job("Software Engineering Student", "Nice to have: 3+ years of experience with Linux")
    assert reject_reason(job, RULES) is None


def test_prefilter_filters_senior_and_experience_jobs():
    assert "בכירה" in reject_reason(_job("Senior Software Engineer"), RULES)
    assert "5+" in reject_reason(_job("Software Engineer", "5+ years of hands-on experience in C++"), RULES)
    assert "3+" in reject_reason(_job("מפתח/ת Backend", "דרישות: 3 שנות ניסיון בפיתוח"), RULES)


def test_prefilter_one_year_passes():  # the search allows up to a year
    assert reject_reason(_job("Software Engineer", "1+ years of experience - an advantage"), RULES) is None


def test_prefilter_field_words_but_not_when_the_title_names_software():
    assert "תחום" in reject_reason(_job("Marketing Student"), RULES)
    assert "תחום" in reject_reason(_job("נציג/ת תמיכה טכנית - מתאים לסטודנטים"), RULES)
    assert reject_reason(_job("סטודנט/ית להנדסת חשמל או מדעי המחשב"), RULES) is None
    assert reject_reason(_job("Data Engineer - Finance Systems"), RULES) is None  # software word: the brain decides
    assert "תחום" in reject_reason(_job("Junior QA & AI Automation Engineer"), RULES)  # QA is out even in software
    assert "תחום" in reject_reason(_job("Sales Development Representative - משרת סטודנט"), RULES)


def test_prefilter_hebrew_word_inside_another_word_is_not_a_match():
    assert reject_reason(_job("סטודנט/ית למחשבים ותוכנה"), RULES) is None


def test_years_asked_takes_the_smallest_number():
    assert years_asked("3+ years of Python experience. 1 year of experience with Docker") == 1
    assert years_asked("At least 2 years remaining for your degree") is None


# ---- dedup ----

def test_senior_and_regular_role_are_not_the_same_job():  # Amazon, 11/10/2026
    board = {"amazon-1": {"agent_id": "amazon:1", "source": "amazon:amazon", "title": "Software Development Engineer, EBS",
                          "company": "Amazon", "location": "Tel Aviv"}}
    senior = {"id": "amazon:2", "source": "amazon:amazon", "title": "Senior Software Development Engineer, EBS",
              "company": "Amazon", "location": "Tel Aviv"}
    assert find_matches(senior, board) == []


def test_two_ids_from_one_site_are_two_jobs():
    board = {"amazon-1": {"agent_id": "amazon:1", "source": "amazon:amazon", "title": "Embedded SW Engineer",
                          "company": "Amazon", "location": "Haifa"}}
    other = {"id": "amazon:2", "source": "amazon:amazon", "title": "Embedded SW Engineer", "company": "Amazon", "location": "Haifa"}
    assert find_matches(other, board) == []


def test_a_job_board_can_list_one_job_twice():  # HireMeTech, 14/10/2026: same Ashdod job, two ids
    board = {"hiremetech-1": {"agent_id": "hiremetech:1", "source": "hiremetech:juniors", "title": "סטודנט/ית מוביל/ת חדשנות",
                              "company": "חסוי — דרך HireMeTech", "location": "Ashdod"}}
    other = {"id": "hiremetech:2", "source": "hiremetech:juniors", "title": "סטודנט/ית מוביל/ת חדשנות",
             "company": "חסוי — דרך HireMeTech", "location": "Ashdod"}
    assert [m.kind for m in find_matches(other, board)] == ["borderline"]


def test_same_role_from_a_company_site_and_a_board_is_still_exact():
    board = {"lever-m-1": {"agent_id": "lever:m:1", "source": "lever:mobileye", "title": "Algorithm Student",
                           "company": "Mobileye", "location": "Jerusalem"}}
    from_board = {"id": "drushim:9", "source": "drushim:drushim", "title": "Algorithm Student", "company": "Mobileye", "location": "Jerusalem"}
    assert [(m.board_id, m.kind) for m in find_matches(from_board, board)] == [("lever-m-1", "exact")]


# ---- prepare's split ----

def test_split_plan_settles_exact_matches_in_code_and_sends_the_rest_to_the_brain():
    board = {"hiremetech-5": {"agent_id": "hiremetech:5", "source": "hiremetech:juniors", "title": "Algorithm Student",
                              "company": "Mobileye", "location": "Jerusalem", "url": "https://hmt/5",
                              "sightings": [{"source": "hiremetech:juniors", "url": "https://hmt/5", "date": "2026-10-10"}]}}
    inbox = [
        {"id": "lever:m:1", "source": "lever:mobileye", "title": "Algorithm Student", "company": "Mobileye", "location": "Jerusalem", "url": "https://lever/1"},
        {"id": "greenhouse:n:7", "source": "greenhouse:nebius", "title": "AI Intern", "company": "Nebius", "location": "Tel Aviv", "url": "https://gh/7"},
        {"id": "drushim:8", "source": "drushim:drushim", "title": "AI Intern", "company": "Nebius", "location": "Tel Aviv", "url": "https://dr/8"},
    ]
    plan = build_plan(board, inbox, TODAY)
    brain, writes, counts = split_plan(plan, board, TODAY)
    assert [b["doc_id"] for b in brain] == ["greenhouse-n-7"]
    assert [s["source"] for s in brain[0]["fields"]["sightings"]] == ["greenhouse:nebius", "drushim:drushim"]
    [w] = writes
    assert w["doc_id"] == "hiremetech-5" and len(w["data"]["sightings"]) == 2
    assert w["data"]["url"] == "https://lever/1"  # the company site becomes the source
    assert counts == {"exact_board": 1, "exact_today": 1}


# ---- job-board agents ----

def test_drushim_job_has_full_text_and_employer():
    from jobhunter.agents import drushim
    raw = json.loads((FIXTURES / "drushim_item.json").read_text(encoding="utf-8"))
    job = drushim.to_job(raw, {"slug": "drushim"})
    assert job["id"] == "drushim:38532098" and job["source"] == "drushim:drushim"
    assert job["company"] == drushim.HIDDEN_COMPANY  # "- חסוי -" on the site
    assert job["location"] == "קריית גת" and job["posted_at"] == "2026-09-24"
    assert "דרישות:" in job["description"] and "AutoCAD" in job["description"]
    assert job["url"] == "https://www.drushim.co.il/job/38532098/a9c2cb21/"


def test_jobmaster_cards_parse():
    from jobhunter.agents import jobmaster
    cards = jobmaster.parse_cards((FIXTURES / "jobmaster_search.html").read_text(encoding="utf-8"))
    assert len(cards) == 2
    first = cards[0]
    assert first["key"].isdigit() and first["title"] and first["company"] and first["city"]
    job = jobmaster.to_job(first, {}, {"slug": "jobmaster"})
    assert job["url"].endswith(f"key={first['key']}") and job["description"]


# ---- public page ----

def test_public_board_embeds_every_job_and_the_marks(tmp_path, monkeypatch):
    """User's decision 16/10/2026: the public site is the board - every tab visible, owner-only changes."""
    from jobhunter import public, overlay
    monkeypatch.chdir(Path(__file__).parent.parent)
    monkeypatch.setattr(overlay, "load", lambda cwd=None: ({"a": {"status": "applied", "history": []}}, None))
    board_dir = tmp_path / "board"
    (board_dir / "jobs").mkdir(parents=True)
    for k, v in {"a": {"title": "Open match", "status": "new", "applied_description": "BIG"}, "b": {"title": "Filtered", "status": "filtered"}}.items():
        (board_dir / "jobs" / f"{k}.json").write_text(json.dumps(v), encoding="utf-8")
    result = public.build(board_dir, tmp_path, TODAY, out_dir=tmp_path / "public")
    html = (tmp_path / "public" / "index.html").read_text(encoding="utf-8")
    assert result["jobs"] == 2 and "Open match" in html and "Filtered" in html and '"applied"' in html
    assert "BIG" not in html  # the stored copy of the description stays out


def test_marks_win_unless_the_card_has_a_newer_event():
    from jobhunter.overlay import merge
    card = {"status": "new", "history": [{"status": "new", "at": "2026-10-14T07:00:00Z"}]}
    mark = {"status": "applied", "applied_at": "2026-10-16", "history": [{"status": "applied", "at": "2026-10-16T10:00:00Z"}]}
    merged = merge(card, mark)
    assert merged["status"] == "applied" and merged["applied_at"] == "2026-10-16" and len(merged["history"]) == 2
    closed = {**card, "status": "closed", "history": card["history"] + [{"status": "closed", "at": "2026-10-20T07:00:00Z"}]}
    assert merge(closed, mark)["status"] == "closed"  # the morning closed it after the mark
    reopened = {**mark, "status": "new", "history": mark["history"] + [{"status": "new", "at": "2026-10-21T08:00:00Z"}]}
    assert merge(closed, reopened)["status"] == "new"  # and the user reopened it after that


def test_jobmaster_links_differ_by_their_key():  # 15/10/2026: every JobMaster job looked like one link
    from jobhunter.dedup import normalize_url
    a = "https://www.jobmaster.co.il/jobs/checknum.asp?key=1"
    b = "https://www.jobmaster.co.il/jobs/checknum.asp?key=2"
    assert normalize_url(a) != normalize_url(b)


def test_two_jobs_matching_one_board_job_make_one_write():
    board = {"lever-m-1": {"agent_id": "lever:m:1", "source": "lever:mobileye", "title": "Algorithm Student",
                           "company": "Mobileye", "location": "Jerusalem", "url": "https://lever/1"}}
    inbox = [{"id": f"drushim:{n}", "source": "drushim:drushim", "title": "Algorithm Student", "company": "Mobileye",
              "location": "Jerusalem", "url": f"https://dr/{n}"} for n in (1, 2)]
    _, writes, _ = split_plan(build_plan(board, inbox, TODAY), board, TODAY)
    assert len(writes) == 1 and len(writes[0]["data"]["sightings"]) == 2


def test_deadline_passed_closes_everything_but_applied():  # user's rule, 16/10/2026
    from jobhunter.morning import deadline_closures
    board = {"a": {"status": "hold", "deadline": "2026-10-13"}, "b": {"status": "applied", "deadline": "2026-10-01"},
             "c": {"status": "new", "deadline": "2026-10-20"}, "d": {"status": "new"}}
    [c] = deadline_closures(board, TODAY)
    assert c["board_id"] == "a" and c["update"]["status"] == "closed" and "מועד ההגשה עבר" in c["update"]["history"][-1]["note"]


def test_closed_applications_are_filtered():
    assert reject_reason(_job("Software Engineering Student", "שימו לב: ההגשה סגורה"), RULES) == "ההגשה סגורה"


def test_hiremetech_closed_job_page_is_marked_and_prefiltered():  # 16/10/2026: the apply button says you can't apply
    from jobhunter.agents.hiremetech import parse_job_page
    page = "Software Engineer Intern\nאי אפשר להגיש למשרה זו\nעל התפקיד\nפיתוח ב-Python\nמשרות דומות\n..."
    parsed = parse_job_page(page)
    assert parsed["description"].startswith("ההגשה סגורה")
    assert reject_reason(_job("Software Engineer Intern", parsed["description"]), RULES) == "ההגשה סגורה"


def test_a_morning_claude_never_finished_goes_back_to_the_queue(tmp_path):  # 21/10/2026
    from jobhunter.morning import done_marker, unfinished_jobs
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "last-prepare.txt").write_text("2026-10-20", encoding="utf-8")
    (tmp_path / "plan" / "2026-10-20.json").write_text(json.dumps({"jobs": [{"inbox_job": {"id": "x:1"}, "matches": []}]}), encoding="utf-8")
    assert [j["id"] for j in unfinished_jobs(tmp_path)] == ["x:1"]
    done_marker(tmp_path, "2026-10-20").parent.mkdir(parents=True)
    done_marker(tmp_path, "2026-10-20").write_text("{}", encoding="utf-8")
    assert unfinished_jobs(tmp_path) == []
