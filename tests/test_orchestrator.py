"""Stage 6 tests, built from real gold-set cases (#1/#12, #14/#15, Amazon #3/#19, FIL #17/#20)."""

from datetime import date, timedelta

from jobhunter.dedup import find_matches, normalize_url, title_words
from jobhunter.morning import build_plan
from jobhunter.retention import compaction_update

TODAY = date(2026, 10, 10)

BOARD = {
    "g01": {"title": "מפתח/ת Java Backend עם התמחות ב-AI", "company": "חסוי (סטארטאפ במרכז) — דרך SQLink",
            "location": "מרכז", "url": "https://juniors.hiremetech.com/job/150083592", "status": "filtered"},
    "g15": {"title": "Junior DevOps Engineer", "company": "משרד ממשלתי — דרך SQLink", "location": "ירושלים",
            "status": "filtered"},
    "g03": {"title": "Software Engineer Student, Virtual Platforms", "company": "Amazon (Annapurna Labs)",
            "status": "new"},
    "g17": {"title": "Junior Software Engineer - Student Position", "company": "FIL Robotics", "status": "new"},
    "g07": {"title": "סטודנט.ית למדמ\"ח /תוכנה - פיתוח", "company": "רפאל", "location": "קריית ביאליק",
            "description": "מיקום: מכון דוד - קריות. מספר משרה: 13053", "status": "filtered"},
}


def kinds(job):
    return [(m.board_id, m.kind) for m in find_matches(job, BOARD)]


def test_same_link_with_tracking_params_is_exact():  # gold #12 = #1
    whatsapp = {"title": "מפתח/ת Java Backend עם התמחות ב-AI עבור חברת סטארטאפ באזור המרכז",
                "url": "https://juniors.hiremetech.com/job/150083592?utm_source=wa_adef4d23&utm_content=wa_clean"}
    assert kinds(whatsapp) == [("g01", "exact")]


def test_same_title_unknown_company_is_borderline():  # gold #14 ~ #15
    whatsapp = {"title": "Devops Engineer - Junior", "location": "Jerusalem"}
    assert kinds(whatsapp) == [("g15", "borderline")]


def test_same_company_other_role_is_not_a_duplicate():  # gold #19 vs #3, #20 vs #17
    spiv = {"title": "Software Engineer Student, SPIV team", "company": "Amazon", "location": "חיפה"}
    qa = {"title": "Junior QA Engineer - Student Position", "company": "FIL Robotics"}
    assert kinds(spiv) == []
    assert kinds(qa) == []


def test_same_job_number_same_company_is_exact():
    again = {"title": "סטודנט/ית לפיתוח תוכנה", "company": "רפאל", "description": "מספר משרה: 13053"}
    assert kinds(again) == [("g07", "exact")]


def test_same_job_number_other_company_is_not_exact():
    other = {"title": "Embedded student", "company": "Elbit Systems", "description": "מספר משרה: 13053"}
    assert kinds(other) == []


def test_hebrew_gender_endings_are_ignored():
    assert title_words("מפתח/ת Backend") == title_words("מפתח Backend")
    assert title_words("סטודנט.ית לפיתוח") == title_words("לפיתוח")


def test_url_normalization_keeps_job_id_params():
    assert normalize_url("https://boards.greenhouse.io/x/jobs?gh_jid=7&utm_source=li") == \
           normalize_url("http://www.boards.greenhouse.io/x/jobs/?gh_jid=7")
    assert normalize_url("https://x.com/jobs?gh_jid=7") != normalize_url("https://x.com/jobs?gh_jid=8")


def test_handled_job_coming_back_carries_its_status():
    board = {"n1": {"title": "Backend Student", "company": "Wix", "url": "https://wix.com/jobs/1", "status": "not_interested"},
             "a1": {"title": "Data Student", "company": "Wix", "url": "https://wix.com/jobs/2", "status": "applied"}}
    inbox = [{"id": "x1", "title": "Backend Student", "url": "https://wix.com/jobs/1/"},
             {"id": "x2", "title": "Data Student", "url": "https://wix.com/jobs/2?ref=glassdoor"}]
    plan = build_plan(board, inbox, TODAY)
    statuses = [[m["board_status"] for m in j["matches"]] for j in plan["jobs"]]
    assert statuses == [["not_interested"], ["applied"]]


def test_same_job_twice_in_one_morning_inbox():
    inbox = [{"id": "glassdoor:1", "title": "Backend Student", "company": "Wix", "url": "https://wix.com/jobs/9"},
             {"id": "hiremetech:5", "title": "Backend Student", "company": "Wix", "url": "https://wix.com/jobs/9"}]
    plan = build_plan({}, inbox, TODAY)
    assert plan["jobs"][0]["matches"] == []
    assert [(m["board_id"], m["kind"]) for m in plan["jobs"][1]["matches"]] == [("inbox:glassdoor:1", "exact")]


def _job(status, days_ago, **extra):
    at = (TODAY - timedelta(days=days_ago)).isoformat() + "T08:00:00Z"
    return {"title": "Backend Student", "company": "Wix", "url": "https://wix.com/jobs/1", "status": status,
            "description": "long text", "requirements_must": ["Java"], "not_interested_reason": "רחוק",
            "history": [{"status": status, "at": at}], **extra}


def test_not_interested_after_31_days_keeps_the_short_line():
    update = compaction_update(_job("not_interested", 31), TODAY)
    assert update["description"] == {"__delete__": True}
    assert update["requirements_must"] == {"__delete__": True}
    for kept in ("title", "company", "url", "status", "not_interested_reason", "history"):
        assert kept not in update


def test_retention_leaves_alone_what_must_stay():
    assert compaction_update(_job("not_interested", 30), TODAY) is None  # exactly 30 days
    assert compaction_update(_job("applied", 400), TODAY) is None       # applied: forever
    assert compaction_update(_job("hold", 90), TODAY) is None           # on hold: forever
    assert compaction_update(_job("closed", 60, compacted="2026-09-01"), TODAY) is None  # already done
