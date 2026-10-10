"""Company agents (stage 8): filters, site formats, the runner. No network - saved site responses in tests/fixtures/.

greenhouse_scaleops.json  real ScaleOps jobs (2 in Tel Aviv, 1 in the US) + 1 edited copy with "students" only in the text
lever_mobileye.json       real Mobileye jobs: a student job, a full-time job in Israel, a job in India
workday_kla.json          real KLA list + texts (an "Internship" only in the text, a student job, a regular job)
                          and NVIDIA's nested location filter
"""

import json
import re
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from jobhunter.agents import __main__ as runner
from jobhunter.agents import greenhouse, http, lever
from jobhunter.agents.filters import html_to_text, is_israel, matching_keyword
from jobhunter.agents.http import FetchError

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = json.loads((Path(__file__).parent.parent / "config" / "sources.json").read_text(encoding="utf-8"))
DAILY = CONFIG["keywords"]["daily"]
WEEKLY = CONFIG["keywords"]["weekly"]
ISRAEL = CONFIG["israel"]
DAY1 = date(2026, 10, 10)
DAY2 = DAY1 + timedelta(days=1)

SCALEOPS = {"company": "ScaleOps", "slug": "scaleops"}
MOBILEYE = {"company": "Mobileye", "slug": "mobileye", "host": "api.eu.lever.co"}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- filters ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("title, expected", [
    ("Software Intern", "Intern"),
    ("Interns program 2027", "Intern"),
    ("Student Position", "Student"),
    ("Summer Internship", "Internship"),
    ("משרת סטודנט", "סטודנט"),
    ("דרושים לסטודנטים", "סטודנט"),
    ("סטודנטית למדעי המחשב", "סטודנט"),
    ("International Sales", None),      # "intern" inside a longer word
    ("Internal Tools Engineer", None),
    ("Studentship", None),
    ("Senior Backend Engineer", None),
])
def test_keywords_are_whole_words(title, expected):
    assert matching_keyword(title, "", DAILY) == expected


def test_keyword_found_only_in_text():
    assert matching_keyword("Software Engineer", "Open to 3rd year students.", DAILY) == "Student"


def test_weekly_words_are_wider():
    assert matching_keyword("Entry-Level Developer", "", DAILY) is None
    assert matching_keyword("Entry-Level Developer", "", WEEKLY) == "Entry Level"
    assert matching_keyword("Outstanding Graduate - ML Engineer", "", WEEKLY) == "Graduate"


@pytest.mark.parametrize("location, country, expected", [
    ("Tel Aviv", None, True),                                   # ScaleOps writes the city only
    ("Tel Aviv District, Israel", None, True),
    ("Amsterdam, Netherlands; Tel Aviv, Israel", None, True),   # one of several places is enough
    ("Jerusalem, Israel", "IL", True),
    ("", "IL", True),                                          # Lever's country code alone
    ("Amsterdam, Netherlands", None, False),
    ("Remote - Europe", None, False),
    ("Palo Alto, California, United States", None, False),
    ("Mumbai, India", "IN", False),
])
def test_is_israel(location, country, expected):
    assert is_israel(location, country, ISRAEL) is expected


def test_html_to_text_keeps_lists_and_unescapes():
    text = html_to_text("&lt;p&gt;About&amp;nbsp;us&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;Java&lt;/li&gt;&lt;/ul&gt;")
    assert text == "About us\n\n- Python\n\n- Java"
    assert html_to_text(None) == ""


# --- site formats ----------------------------------------------------------------------------------

def test_greenhouse_israel_and_keywords(monkeypatch):
    monkeypatch.setattr(greenhouse, "fetch_json", lambda url: fixture("greenhouse_scaleops.json"))
    jobs, stats = greenhouse.fetch(SCALEOPS, ISRAEL, DAILY)

    assert stats == {"total": 4, "site_total": 4, "israel": 3, "matched": 1}
    [job] = jobs
    assert job["id"] == "greenhouse:scaleops:999000001"
    assert job["source"] == "greenhouse:scaleops"
    assert job["company"] == "ScaleOps"
    assert job["location"] == "Tel Aviv"
    assert job["matched_keyword"] == "Student"
    assert "- Python" in job["description"] and "&lt;" not in job["description"]


def test_greenhouse_job_fields():
    raw = fixture("greenhouse_scaleops.json")["jobs"][0]
    job = greenhouse.to_job(raw, SCALEOPS)
    assert job["id"] == f"greenhouse:scaleops:{raw['id']}"
    assert job["url"] == raw["absolute_url"]
    assert job["job_number"] == raw["requisition_id"]
    assert job["posted_at"] == raw["first_published"][:10]
    assert job["description"] and "<" not in job["description"]


def test_lever_israel_and_keywords(monkeypatch):
    monkeypatch.setattr(lever, "fetch_json", lambda url: fixture("lever_mobileye.json"))
    jobs, stats = lever.fetch(MOBILEYE, ISRAEL, DAILY)

    assert stats["total"] == 3 and stats["israel"] == 2 and stats["matched"] == 1
    [job] = jobs
    assert job["title"] == "Algorithm SW Developer Student - Calibration Team"
    assert job["id"] == "lever:mobileye:bbeb4626-09ea-4975-b5a2-56e4441b8784"
    assert job["url"].startswith("https://jobs.eu.lever.co/mobileye/")
    assert job["apply_url"].endswith("/apply")
    assert job["location"] == "Jerusalem, Israel"
    assert job["posted_at"] == "2026-10-08"
    assert "All you need is:" in job["description"]  # the lists are part of the text


def test_lever_commitment_counts_for_keywords(monkeypatch):
    """A Lever job tagged commitment=Student passes even if neither title nor text says so."""
    raw = fixture("lever_mobileye.json")[1]
    raw["categories"]["commitment"] = "Student"
    monkeypatch.setattr(lever, "fetch_json", lambda url: [raw])
    jobs, _ = lever.fetch(MOBILEYE, ISRAEL, DAILY)
    assert [j["matched_keyword"] for j in jobs] == ["Student"]
    assert "Student" not in jobs[0]["description"].split("\n")[-1]  # the tag is not added to the job text


# --- fetch_json ------------------------------------------------------------------------------------

def _fake_requests(monkeypatch, outcomes):
    """Each call to the site returns / raises the next outcome. Returns the list of calls made."""
    calls = []

    def fake(url, body):
        calls.append(url)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(http, "_request_once", fake)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    return calls


def _http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


def test_fetch_retries_once_on_server_error(monkeypatch):
    calls = _fake_requests(monkeypatch, [_http_error(503), b'{"ok": 1}'])
    assert http.fetch_json("https://x") == {"ok": 1}
    assert len(calls) == 2


def test_fetch_does_not_retry_when_blocked(monkeypatch):
    calls = _fake_requests(monkeypatch, [_http_error(403)])
    with pytest.raises(FetchError, match="403"):
        http.fetch_json("https://x")
    assert len(calls) == 1


def test_fetch_gives_up_after_second_network_error(monkeypatch):
    calls = _fake_requests(monkeypatch, [urllib.error.URLError("down"), urllib.error.URLError("down")])
    with pytest.raises(FetchError, match="network error"):
        http.fetch_json("https://x")
    assert len(calls) == 2


def test_fetch_rejects_a_body_that_is_not_json(monkeypatch):
    _fake_requests(monkeypatch, [b"<html>blocked</html>"])
    with pytest.raises(FetchError, match="not JSON"):
        http.fetch_json("https://x")


# --- the runner ------------------------------------------------------------------------------------

def _config(*extra_greenhouse):
    return {**CONFIG, "systems": {"greenhouse": [SCALEOPS, *extra_greenhouse], "lever": [MOBILEYE]}}


@pytest.fixture
def offline_sites(monkeypatch):
    """Both agents read the saved responses; any other slug fails like a missing company (404)."""
    def gh(url):
        if "/scaleops/" not in url:
            raise FetchError(f"HTTP 404 from {url}")
        return fixture("greenhouse_scaleops.json")

    monkeypatch.setattr(greenhouse, "fetch_json", gh)
    monkeypatch.setattr(lever, "fetch_json", lambda url: fixture("lever_mobileye.json"))


def test_second_run_adds_nothing(tmp_path, offline_sites):
    """The stage 8 pass test: two runs in a row, the second finds no new jobs."""
    first = runner.run_all(_config(), tmp_path, DAY1)
    second = runner.run_all(_config(), tmp_path, DAY2)

    assert first["new"] == 2 and first["errors"] == [] and first["warnings"] == []
    assert second["new"] == 0
    inbox = json.loads((tmp_path / "inbox" / f"{DAY1}.json").read_text(encoding="utf-8"))
    assert {j["id"] for j in inbox} == {"greenhouse:scaleops:999000001",
                                        "lever:mobileye:bbeb4626-09ea-4975-b5a2-56e4441b8784"}
    assert (tmp_path / "seen" / "greenhouse-scaleops.json").exists()
    assert (tmp_path / "seen" / "lever-mobileye.json").exists()


def test_failing_site_does_not_stop_the_run(tmp_path, offline_sites):
    report = runner.run_all(_config({"company": "Broken Co", "slug": "broken"}), tmp_path, DAY1)

    assert report["new"] == 2  # the other companies still ran
    assert report["errors"] == ["Broken Co: FetchError: HTTP 404 from https://boards-api.greenhouse.io/v1/boards/broken/jobs?content=true"]
    assert not (tmp_path / "seen" / "greenhouse-broken.json").exists()  # nothing marked as seen


def test_failure_keeps_what_was_seen_before(tmp_path, offline_sites, monkeypatch):
    """A site that fails today must not lose its memory - tomorrow its old jobs are still not new."""
    runner.run_all(_config(), tmp_path, DAY1)
    seen_file = tmp_path / "seen" / "lever-mobileye.json"
    before = seen_file.read_text(encoding="utf-8")

    def down(url):
        raise FetchError("network error")
    monkeypatch.setattr(lever, "fetch_json", down)
    runner.run_all(_config(), tmp_path, DAY2)

    assert seen_file.read_text(encoding="utf-8") == before


def test_warns_when_a_company_drops_to_zero(tmp_path, offline_sites, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / f"{DAY1}-agents.json").write_text(json.dumps(
        {"companies": [{"source": "greenhouse:scaleops", "israel": 32}]}), encoding="utf-8")
    monkeypatch.setattr(greenhouse, "fetch_json", lambda url: {"jobs": [], "meta": {"total": 0}})

    report = runner.run_all(_config(), tmp_path, DAY2)
    assert report["warnings"] == ["ScaleOps: 0 jobs in Israel today, 32 last run - the site may have changed"]


def test_main_writes_the_report(tmp_path, offline_sites, monkeypatch, capsys):
    config_file = tmp_path / "sources.json"
    config_file.write_text(json.dumps(_config(), ensure_ascii=False), encoding="utf-8")

    assert runner.main(["run", "--today", str(DAY1), "--state", str(tmp_path), "--config", str(config_file)]) == 0
    report = json.loads((tmp_path / "runs" / f"{DAY1}-agents.json").read_text(encoding="utf-8"))
    assert report["kind"] == "daily" and report["new"] == 2
    assert '"new": 2' in capsys.readouterr().out


# --- Workday ---------------------------------------------------------------------------------------

KLA = {"company": "KLA", "slug": "kla", "host": "kla.wd1.myworkdayjobs.com", "tenant": "kla", "site": "Search"}


@pytest.fixture
def workday_site(monkeypatch):
    """A fake KLA Workday site from saved responses. Pages of 2, total sent on the first page only (like Workday).
    .details lists the job-text requests made; .site["total"] is what the site claims."""
    from jobhunter.agents import workday
    saved = fixture("workday_kla.json")
    detail_calls = []
    site = {"total": len(saved["postings"])}

    def fake(url, data=None):
        if url.endswith("/jobs"):
            if not data["appliedFacets"]:
                return {"facets": saved["facets"], "total": 1077, "jobPostings": []}
            assert data["appliedFacets"] == {"Country": ["084562884af243748dad7c84c304d89a"]}
            offset = data["offset"]
            return {"total": site["total"] if offset == 0 else 0,
                    "jobPostings": saved["postings"][offset:offset + workday.PAGE_SIZE]}
        path = url.split("/Search", 1)[1]
        detail_calls.append(path)
        return {"jobPostingInfo": saved["details"][path]}

    monkeypatch.setattr(workday, "fetch_json", fake)
    monkeypatch.setattr(workday, "PAGE_SIZE", 2)
    return SimpleNamespace(details=detail_calls, site=site)


def test_workday_finds_the_israel_filter_flat_and_nested():
    from jobhunter.agents import workday
    saved = fixture("workday_kla.json")
    assert workday.israel_facet(saved["facets"]) == {"Country": ["084562884af243748dad7c84c304d89a"]}
    nested = workday.israel_facet([saved["nvidia_location_facet"]])  # NVIDIA: locationMainGroup -> locationHierarchy1
    assert list(nested) == ["locationHierarchy1"]
    with pytest.raises(FetchError, match="Israel"):
        workday.israel_facet([{"facetParameter": "Country", "values": [{"descriptor": "Germany", "id": "x"}]}])


def test_workday_pages_filters_and_formats(tmp_path, workday_site):
    from jobhunter.agents import workday
    jobs, stats = workday.fetch(KLA, ISRAEL, DAILY, tmp_path / "cache")

    assert stats == {"total": 3, "site_total": 3, "israel": 3, "matched": 2, "texts_fetched": 3}
    by_title = {j["title"]: j for j in jobs}
    assert set(by_title) == {"Software Developer", "Research Scientist Student"}
    assert by_title["Software Developer"]["matched_keyword"] == "Internship"  # only in the text
    job = by_title["Research Scientist Student"]
    assert job["id"].startswith("workday:kla:") and job["source"] == "workday:kla"
    assert job["url"].startswith("https://kla.wd1.myworkdayjobs.com/Search/job/")
    assert job["job_number"] and job["posted_at"] and "Israel" in job["location"]
    assert job["description"] and "<" not in job["description"]


def test_workday_texts_are_fetched_once(tmp_path, workday_site):
    from jobhunter.agents import workday
    workday.fetch(KLA, ISRAEL, DAILY, tmp_path / "cache")
    workday_site.details.clear()
    jobs, stats = workday.fetch(KLA, ISRAEL, WEEKLY, tmp_path / "cache")  # other keywords, same cached texts

    assert workday_site.details == [] and stats["texts_fetched"] == 0
    assert len(jobs) >= 2


def test_workday_forgets_texts_of_jobs_that_left(tmp_path, workday_site):
    from jobhunter.agents import workday
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "OLD-1.json").write_text("{}", encoding="utf-8")
    workday.fetch(KLA, ISRAEL, DAILY, cache)

    assert not (cache / "OLD-1.json").exists()
    assert len(list(cache.glob("*.json"))) == 3


def test_workday_count_mismatch_is_an_error(tmp_path, workday_site):
    from jobhunter.agents import workday
    workday_site.site["total"] = 5  # the site says 5, only 3 can be listed
    with pytest.raises(FetchError, match="listed 3 jobs in Israel but the site says 5"):
        workday.fetch(KLA, ISRAEL, DAILY, tmp_path / "cache")


def test_runner_gives_workday_its_cache(tmp_path, workday_site):
    config = {**CONFIG, "systems": {"workday": [KLA]}}
    report = runner.run_all(config, tmp_path, DAY1)

    assert report["new"] == 2 and report["errors"] == []
    assert len(list((tmp_path / "cache" / "workday-kla").glob("*.json"))) == 3
    assert (tmp_path / "seen" / "workday-kla.json").exists()


def test_fetch_waits_and_retries_once_on_429(monkeypatch):
    """Too Many Requests (Qualcomm): wait what the site asks for (Retry-After), else 30s, then one retry."""
    waits = []
    for headers, expected in (({"Retry-After": "7"}, 7.0), ({}, 30.0)):
        outcomes = [urllib.error.HTTPError("https://x", 429, "slow down", headers, None), b'{"ok": 1}']
        calls = _fake_requests(monkeypatch, outcomes)
        monkeypatch.setattr(http.time, "sleep", waits.append)
        assert http.fetch_json("https://x") == {"ok": 1}
        assert len(calls) == 2 and waits[-1] == expected


def test_fetch_gives_up_after_second_429(monkeypatch):
    calls = _fake_requests(monkeypatch, [urllib.error.HTTPError("https://x", 429, "slow down", {}, None)] * 2)
    with pytest.raises(FetchError, match="429"):
        http.fetch_json("https://x")
    assert len(calls) == 2


# --- Eightfold -------------------------------------------------------------------------------------

QUALCOMM = {"company": "Qualcomm", "slug": "qualcomm", "host": "careers.qualcomm.com", "domain": "qualcomm.com", "api": "pcsx"}
TEVA = {"company": "Teva", "slug": "teva", "host": "www.careers.teva", "domain": "tevapharm.com", "api": "apply_v2"}


@pytest.fixture
def eightfold_sites(monkeypatch):
    """Fake Qualcomm (pcsx API) and Teva (apply_v2 API) from saved responses, one position per page.
    .details lists the job-text requests made; .count overrides what a site claims."""
    from jobhunter.agents import eightfold
    saved = fixture("eightfold.json")
    state = SimpleNamespace(details=[], count={})

    def page(name, url):
        start = int(re.search(r"start=(\d+)", url).group(1))
        positions = saved[name]["positions"]
        return {"count": state.count.get(name, len(positions)), "positions": positions[start:start + 1]}

    def fake(url, data=None):
        if "/api/pcsx/search" in url:
            return {"data": page("qualcomm", url)}
        if "/api/apply/v2/jobs?" in url:
            return page("teva", url)
        position_id = re.search(r"position_id=(\d+)|/jobs/(\d+)", url)
        position_id = position_id.group(1) or position_id.group(2)
        state.details.append(position_id)
        name = "qualcomm" if "pcsx" in url else "teva"
        return saved[name]["details"][position_id]

    monkeypatch.setattr(eightfold, "fetch_json", fake)
    return state


def test_eightfold_pcsx_api(tmp_path, eightfold_sites):
    from jobhunter.agents import eightfold
    jobs, stats = eightfold.fetch(QUALCOMM, ISRAEL, DAILY, tmp_path / "cache")

    assert stats == {"total": 2, "site_total": 2, "israel": 2, "matched": 1, "texts_fetched": 2}
    [job] = jobs
    assert job["title"].startswith("FY26 Intern - Camera Algorithm") and job["matched_keyword"] == "Intern"
    assert job["id"].startswith("eightfold:qualcomm:") and job["source"] == "eightfold:qualcomm"
    assert job["url"].startswith("https://careers.qualcomm.com/careers/job/")
    assert job["job_number"] and job["posted_at"] and "Israel" in job["location"]
    assert job["description"] and "<" not in job["description"]


def test_eightfold_apply_v2_api_and_leaky_location_filter(tmp_path, eightfold_sites):
    """Teva's site lists a job in Atlanta under Israel - the code drops it."""
    from jobhunter.agents import eightfold
    jobs, stats = eightfold.fetch(TEVA, ISRAEL, DAILY, tmp_path / "cache")
    assert stats["total"] == 2 and stats["israel"] == 1

    israeli = next(p for p in fixture("eightfold.json")["teva"]["positions"] if "Israel" in p["locations"][0])
    job = eightfold.to_job(str(israeli["id"]), eightfold._fetch_detail(TEVA, str(israeli["id"])), TEVA)
    assert job["title"] == israeli["name"] and job["job_number"]
    assert job["url"].startswith("https://www.careers.teva/careers/job/") and job["posted_at"]


def test_eightfold_texts_are_fetched_once(tmp_path, eightfold_sites):
    from jobhunter.agents import eightfold
    eightfold.fetch(QUALCOMM, ISRAEL, DAILY, tmp_path / "cache")
    eightfold_sites.details.clear()
    _, stats = eightfold.fetch(QUALCOMM, ISRAEL, WEEKLY, tmp_path / "cache")
    assert eightfold_sites.details == [] and stats["texts_fetched"] == 0


def test_eightfold_count_mismatch_is_an_error(tmp_path, eightfold_sites):
    from jobhunter.agents import eightfold
    eightfold_sites.count["qualcomm"] = 5
    with pytest.raises(FetchError, match="listed 2 jobs but the site says 5"):
        eightfold.fetch(QUALCOMM, ISRAEL, DAILY, tmp_path / "cache")


def test_runner_gives_eightfold_its_cache(tmp_path, eightfold_sites):
    report = runner.run_all({**CONFIG, "systems": {"eightfold": [QUALCOMM, TEVA]}}, tmp_path, DAY1)
    assert report["errors"] == [] and report["new"] == 1
    assert len(list((tmp_path / "cache" / "eightfold-teva").glob("*.json"))) == 2
