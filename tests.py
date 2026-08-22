"""Checks on the Argus persistence, discovery, and dashboard seams.

Run: python tests.py
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discover
import store
from dashboard import APPLIED_ROUTE, _build_html, render, score_job

# the module-global path is the persistence seam: point it at a tmp dir
store.CSV_PATH = Path(tempfile.mkdtemp()) / "jobs.csv"


def job_at(days_ago: int, **kw) -> dict:
    published = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(store.UTC_FMT)
    return {"title": "", "summary": "", "location": "", "published": published, **kw}


def full_job(job_id: str, days_ago: int, title: str = "") -> dict:
    return {**job_at(days_ago, title=title), "id": job_id, "company": "", "source": "",
            "link": f"https://example.com/{job_id}", "status": "new"}


def test_suite() -> None:
    now = datetime.now(timezone.utc)
    JOB = {
        "id": "j1", "title": "Data Analyst", "company": "Acme", "location": "Remote",
        "source": "Test", "link": "https://example.com/j1",
        "published": now.strftime(store.UTC_FMT),
        "status": "new", "status_date": "", "summary": "sql",
    }

    # missing file loads as empty; add_jobs appends and round-trips
    assert store.load_jobs() == []
    store.add_jobs([JOB])
    store.add_jobs([{**JOB, "id": "j2"}])
    jobs = store.load_jobs()
    assert [j["id"] for j in jobs] == ["j1", "j2"]
    assert jobs[0]["title"] == "Data Analyst"

    # set_status: unknown id and unknown status are no-ops; a known pair stamps the date
    assert store.set_status("nope", "applied") is False
    assert store.set_status("j1", "hired") is False
    assert store.set_status("j1", "applied") is True
    j1 = next(j for j in store.load_jobs() if j["id"] == "j1")
    assert j1["status"] == "applied"
    assert j1["status_date"] == now.strftime(store.DATE_FMT)
    # untouched rows keep 'new'; a blank column reads as 'new' too
    assert store.get_status(next(j for j in store.load_jobs() if j["id"] == "j2")) == "new"
    assert store.get_status({}) == "new" and store.get_status({"status": " Applied "}) == "applied"

    # this_week keeps recent rows; garbage dates sort as oldest-possible
    rows = [
        {"d": (now - timedelta(days=1)).strftime(store.DATE_FMT)},
        {"d": (now - timedelta(days=10)).strftime(store.DATE_FMT)},
        {"d": "garbage"},
    ]
    assert store.this_week(rows, "d") == [rows[0]]
    assert store.parse_date("garbage", store.DATE_FMT) == datetime.min.replace(tzinfo=timezone.utc)

    # sanitize_html strips tags, decodes entities, collapses whitespace
    assert discover.sanitize_html("<p>Data &amp;  Analyst</p>") == "Data & Analyst"
    assert discover.sanitize_html("<br/>Remote\n\n  (EU)") == "Remote (EU)"
    assert discover.sanitize_html("") == ""

    JOBS = [
        {
            "id": "evil1",
            "title": "<script>alert(1)</script> Data Analyst",
            "source": "RemoteOK",
            "published": "2026-07-01 10:00 UTC",
            "link": "https://example.com/job/evil1",
            "status": "new",
            "_score": 90,
        },
        {
            "id": "done1",
            "title": "Business Analyst",
            "company": "Globex",
            "source": "WWR",
            "published": "2026-06-20 10:00 UTC",
            "status_date": "2026-06-21",
            "link": "https://example.com/job/done1",
            "status": "applied",
            "_score": 40,
        },
    ]

    html = _build_html(
        total_jobs=2, jobs_week=1, feed_breakdown=[("RemoteOK", 1), ("WWR", 1)],
        ranked_jobs=JOBS, total_apps=1, apps_week=0, recent_apps=[JOBS[1]],
    )

    # untrusted feed title must be escaped, never raw
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html

    # pending job gets an Apply link + inline mark button; applied job gets neither
    assert "href='https://example.com/job/evil1'" in html  # Apply links straight to the posting
    assert "<button class='mark' data-id='evil1'>" in html
    assert "data-id='done1'" not in html
    assert "<span class='muted'>Applied</span>" in html
    assert "class=done" in html

    # the mark button POSTs to APPLIED_ROUTE; the old localStorage flow is gone
    assert f"'{APPLIED_ROUTE}'" in html
    assert "localStorage" not in html and "confirm(" not in html

    # Recent Applications panel lists the applied job, newest status_date first
    assert "Recent Applications" in html
    assert "<td>Globex</td>" in html and "2026-06-21" in html

    # --- score_job: freshness buckets, title/location match, skill cap ---
    assert score_job(job_at(0)) == 50
    assert score_job(job_at(2)) == 40
    assert score_job(job_at(5)) == 25
    assert score_job(job_at(10)) == 10
    assert score_job(job_at(20)) == 0
    assert score_job(job_at(20, title="Senior Data Analyst")) == 30
    assert score_job(job_at(20, title="Business Analyst")) == 20
    assert score_job(job_at(20, location="Remote")) == 20
    assert score_job(job_at(20, location="Pune")) == 0  # no location keyword
    assert score_job(job_at(20, summary="sql python power bi tableau excel etl")) == 25  # 6 skills capped

    # --- render: higher score first, ties stay newest-first ---
    store.add_jobs([
        full_job("lo_old", 18),
        full_job("hi", 20, title="Data Analyst"),
        full_job("lo_new", 16),
    ])
    page = render()
    assert page.index("data-id='hi'") < page.index("data-id='lo_new'") < page.index("data-id='lo_old'")

    print("OK: tests passed")


if __name__ == "__main__":
    test_suite()
