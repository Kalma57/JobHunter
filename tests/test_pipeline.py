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


def test_workday_entry_without_a_link_is_skipped(monkeypatch):  # NVIDIA, 21/10/2026
    from jobhunter.agents import workday
    pages = [{"facets": [{"facetParameter": "country", "values": [{"descriptor": "Israel", "id": "IL"}]}]},
             {"total": 2, "jobPostings": [{"externalPath": "/job/a_JR1", "title": "A"}, {"title": "odd entry"}]}]
    monkeypatch.setattr(workday, "_list_page", lambda company, facets, offset: pages[0] if not facets else pages[1])
    postings, total = workday.list_israel({"host": "h", "tenant": "t", "site": "s"})
    assert [p["externalPath"] for p in postings] == ["/job/a_JR1"] and total == 2


def test_closed_for_over_a_week_leaves_the_board():  # user's rule, 21/10/2026
    from jobhunter.morning import removals
    board = {"old": {"status": "closed", "history": [{"status": "closed", "at": "2026-10-05T07:00:00Z"}]},
             "recent": {"status": "closed", "history": [{"status": "closed", "at": "2026-10-10T07:00:00Z"}]},
             "applied": {"status": "applied", "history": [{"status": "applied", "at": "2026-09-01T07:00:00Z"}]}}
    assert removals(board, TODAY) == ["old"]
    plan = build_plan(board, [], TODAY)
    _, writes, _ = split_plan(plan, board, TODAY)
    assert [(w["op"], w["doc_id"]) for w in writes] == [("delete", "old")]


def test_sitemap_agent_keeps_israel_jobs_and_reads_json_ld():  # Intuit / Synopsys, 21/10/2026
    from jobhunter.agents import sitemap
    xml = """<urlset><url><loc>https://jobs.x.com/job/petah-tikva/software-engineer-intern/27595/111</loc></url>
             <url><loc>https://jobs.x.com/job/toronto/intern/27595/222</loc></url>
             <url><loc>https://jobs.x.com/category/software/27595/1</loc></url></urlset>"""
    assert sitemap.job_urls(xml, "jobs.x.com", sitemap.ISRAEL_CITIES) == ["https://jobs.x.com/job/petah-tikva/software-engineer-intern/27595/111"]
    page = '<script type="application/ld+json">{"@type": "JobPosting", "title": "Software Engineer Intern", "description": "<p>Python</p>", "datePosted": "2026-10-04T00:00:00", "jobLocation": [{"@type": "Place", "address": {"addressLocality": "Petach Tikva", "addressCountry": "Israel"}}]}</script>'
    posting = sitemap.job_posting(page)
    assert posting["title"] == "Software Engineer Intern" and posting["description"] == "Python"
    assert posting["posted_at"] == "2026-10-04" and posting["location"] == "Petach Tikva, Israel"


def test_the_code_writes_the_board_itself(tmp_path):  # 6/11/2026: no app tool between the code and the board
    from jobhunter import store
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "a.json").write_text(json.dumps({"title": "A", "description": "long", "sightings": []}), encoding="utf-8")
    (tmp_path / "jobs" / "b.json").write_text(json.dumps({"title": "B"}), encoding="utf-8")
    counts = store.apply_writes(tmp_path, [
        {"op": "update", "doc_id": "a", "data": {"sightings": [{"source": "x"}], "description": {"__delete__": True}}},
        {"op": "delete", "doc_id": "b", "data": None}])
    a = json.loads((tmp_path / "jobs" / "a.json").read_text(encoding="utf-8"))
    assert counts == {"updated": 1, "deleted": 1, "missing": 0}
    assert a["sightings"] == [{"source": "x"}] and "description" not in a and not (tmp_path / "jobs" / "b.json").exists()


def test_cards_become_board_jobs_or_merge_into_one(tmp_path):
    from jobhunter import store
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "old.json").write_text(json.dumps({"title": "Old", "status": "hold", "sightings": [{"source": "s1"}]}), encoding="utf-8")
    brain = [{"doc_id": f"n{i}", "fields": {"agent_id": f"x:{i}", "sightings": [{"source": f"s{i + 2}"}]},
              "history_note": "found", "job": {"title": f"T{i}"}, "borderline": []} for i in range(3)]
    cards = [{"doc_id": "n0", "title": "T0", "status": "new", "relevance": {"pass": True}},
             {"doc_id": "n1", "duplicate_of": "old", "duplicate_reason": "same"}]
    counts, missing = store.apply_cards(tmp_path, brain, cards, "2026-11-06")
    new = json.loads((tmp_path / "jobs" / "n0.json").read_text(encoding="utf-8"))
    old = json.loads((tmp_path / "jobs" / "old.json").read_text(encoding="utf-8"))
    assert new["status"] == "new" and new["agent_id"] == "x:0" and new["history"][0]["at"] == "2026-11-06T07:00:00Z"
    assert old["status"] == "hold" and len(old["sightings"]) == 2 and old["alerts"]
    assert counts["passed"] == 1 and counts["merged"] == 1 and [m["doc_id"] for m in missing] == ["n2"]


def test_a_duplicate_of_a_job_from_the_same_morning_merges(tmp_path):  # 8/11/2026
    from jobhunter import store
    (tmp_path / "jobs").mkdir()
    brain = [{"doc_id": "hiremetech-9", "fields": {"sightings": [{"source": "hiremetech:juniors"}]}, "history_note": "n", "job": {"title": "T"}, "borderline": [{}]},
             {"doc_id": "workday-intel-J1", "fields": {"agent_id": "workday:intel:J1", "sightings": [{"source": "workday:intel"}]}, "history_note": "n", "job": {"title": "T"}, "borderline": []}]
    cards = [{"doc_id": "hiremetech-9", "duplicate_of": "inbox:workday:intel:J1"}, {"doc_id": "workday-intel-J1", "title": "T", "status": "filtered"}]
    counts, _ = store.apply_cards(tmp_path, brain, cards, "2026-11-08")
    assert counts["merged"] == 1 and not (tmp_path / "jobs" / "hiremetech-9.json").exists()
    intel = json.loads((tmp_path / "jobs" / "workday-intel-J1.json").read_text(encoding="utf-8"))
    assert len(intel["sightings"]) == 2



def test_the_hourly_task_runs_once_a_day(tmp_path):  # 9/11/2026
    from jobhunter.morning import due, done_marker
    assert due(tmp_path, TODAY)[0]
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "running.lock").write_text("x")
    assert not due(tmp_path, TODAY)[0]                     # a run is going
    (tmp_path / "plan" / "running.lock").unlink()
    done_marker(tmp_path, TODAY.isoformat()).parent.mkdir(parents=True)
    done_marker(tmp_path, TODAY.isoformat()).write_text("{}")
    assert not due(tmp_path, TODAY)[0]                     # already done today



def test_a_failing_morning_stops_after_three_attempts(tmp_path):
    from jobhunter.morning import due, MAX_ATTEMPTS
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / f"attempts-{TODAY.isoformat()}.txt").write_text(str(MAX_ATTEMPTS))
    assert not due(tmp_path, TODAY)[0]



def test_a_day_with_most_sources_unread_is_not_done(tmp_path):  # 9/11/2026: no network right after a wake-up
    from jobhunter.morning import apply_brain, done_marker
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "next.json").write_text(json.dumps({"date": "2026-11-09"}), encoding="utf-8")
    (plan / "2026-11-09-brain.json").write_text("[]", encoding="utf-8")
    (plan / "2026-11-09-run.json").write_text(json.dumps({"sources_read": 3, "sources_total": 39}), encoding="utf-8")
    (tmp_path / "board" / "jobs").mkdir(parents=True)
    result = apply_brain(tmp_path, tmp_path / "board")
    assert "another attempt" in result["apply"] and not done_marker(tmp_path, "2026-11-09").exists()
    (plan / "2026-11-09-run.json").write_text(json.dumps({"sources_read": 38, "sources_total": 39}), encoding="utf-8")
    apply_brain(tmp_path, tmp_path / "board")
    assert done_marker(tmp_path, "2026-11-09").exists()


def test_cards_already_applied_are_not_requeued(tmp_path):
    from jobhunter.morning import unfinished_jobs
    (tmp_path / "plan" / "applied").mkdir(parents=True)
    (tmp_path / "plan" / "last-prepare.txt").write_text("2026-11-09", encoding="utf-8")
    (tmp_path / "plan" / "2026-11-09.json").write_text(json.dumps({"jobs": [{"inbox_job": {"id": "x:1"}}]}), encoding="utf-8")
    assert [j["id"] for j in unfinished_jobs(tmp_path)] == ["x:1"]
    (tmp_path / "plan" / "applied" / "2026-11-09.txt").write_text("1", encoding="utf-8")
    assert unfinished_jobs(tmp_path) == []



def test_computer_engineering_student_titles_reach_the_brain():  # user's feedback 10/11/2026: EE/CE can be relevant
    assert reject_reason(_job('סטודנט/ית להנדסת חשמל או הנדסת מחשבים'), RULES) is None
    assert reject_reason(_job("Electrical / Computer Engineering Student"), RULES) is None
    assert "תחום" in reject_reason(_job("סטודנט/ית להנדסת מכונות"), RULES)  # a degree with no link to software still goes


def test_a_failed_brain_tells_the_user_once_a_day(tmp_path, monkeypatch):  # 10/11/2026: weeks passed unnoticed
    import jobhunter.morning as m
    sent = []
    monkeypatch.setattr(m, "notify", lambda title, text: sent.append((title, text)) or True)
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "next.json").write_text(json.dumps({"date": "2026-11-10"}), encoding="utf-8")
    (plan / "2026-11-10-brain.json").write_text(json.dumps([{"doc_id": "a", "fields": {"sightings": []}, "history_note": "n", "job": {"title": "T"}, "borderline": []}]), encoding="utf-8")
    (plan / "2026-11-10-brain-status.json").write_text(json.dumps({"report": "Not logged in · Please run /login"}), encoding="utf-8")
    (tmp_path / "board" / "jobs").mkdir(parents=True)
    m.apply_brain(tmp_path, tmp_path / "board")
    m.apply_brain(tmp_path, tmp_path / "board")  # the hourly retry
    assert len(sent) == 1 and "claude auth login" in sent[0][1]
