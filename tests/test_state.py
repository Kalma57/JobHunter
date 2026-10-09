from datetime import date, timedelta

from jobhunter.state import Inbox, SeenStore, collect_new

DAY1 = date(2026, 10, 10)
DAY2 = DAY1 + timedelta(days=1)


def jobs(*ids):
    return [{"id": i, "title": f"Job {i}"} for i in ids]


def test_second_run_adds_nothing(tmp_path):
    """The stage 5 pass test: two runs over the same site, the second adds nothing."""
    seen_file = tmp_path / "seen" / "lever.json"
    inbox = Inbox(tmp_path / "inbox")

    assert collect_new(jobs("a", "b", "c"), SeenStore(seen_file), inbox, DAY1) == 3
    # A fresh SeenStore reads from disk, exactly like the next morning's run.
    assert collect_new(jobs("a", "b", "c"), SeenStore(seen_file), inbox, DAY2) == 0

    assert [j["id"] for j in inbox.read(DAY1)] == ["a", "b", "c"]
    assert inbox.read(DAY2) == []


def test_only_the_new_job_reaches_the_inbox(tmp_path):
    seen_file = tmp_path / "seen.json"
    inbox = Inbox(tmp_path / "inbox")
    collect_new(jobs("a", "b"), SeenStore(seen_file), inbox, DAY1)

    assert collect_new(jobs("a", "b", "new"), SeenStore(seen_file), inbox, DAY2) == 1
    assert [j["id"] for j in inbox.read(DAY2)] == ["new"]


def test_same_day_rerun_does_not_duplicate(tmp_path):
    """If the morning run is started twice on one day, the inbox still holds each job once."""
    seen_file = tmp_path / "seen.json"
    inbox = Inbox(tmp_path / "inbox")
    collect_new(jobs("a"), SeenStore(seen_file), inbox, DAY1)
    collect_new(jobs("a"), SeenStore(seen_file), inbox, DAY1)
    assert len(inbox.read(DAY1)) == 1


def test_id_unseen_for_31_days_is_forgotten(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    store.mark_seen("old", DAY1)
    store.mark_seen("borderline", DAY1 + timedelta(days=1))

    forgotten = store.prune(DAY1 + timedelta(days=31))

    assert forgotten == ["old"]
    assert store.is_new("old")
    assert not store.is_new("borderline")  # exactly 30 days: kept


def test_job_still_on_site_is_never_forgotten(tmp_path):
    """Seeing a job again refreshes its date, so a long-open job doesn't come back as new."""
    seen_file = tmp_path / "seen.json"
    inbox = Inbox(tmp_path / "inbox")
    for offset in range(0, 61, 10):
        collect_new(jobs("long-open"), SeenStore(seen_file), inbox, DAY1 + timedelta(days=offset))
    assert len(inbox.read(DAY1)) == 1
    assert all(inbox.read(DAY1 + timedelta(days=o)) == [] for o in range(10, 61, 10))


def test_missing_files_start_empty(tmp_path):
    assert len(SeenStore(tmp_path / "nope.json")) == 0
    assert Inbox(tmp_path / "nope").read(DAY1) == []


def test_hebrew_survives_a_round_trip(tmp_path):
    inbox = Inbox(tmp_path / "inbox")
    inbox.add(DAY1, [{"id": "h1", "title": "סטודנט/ית לפיתוח"}])
    assert inbox.read(DAY1)[0]["title"] == "סטודנט/ית לפיתוח"
