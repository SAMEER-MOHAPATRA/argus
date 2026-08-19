"""Checks on the _build_html seam: escaping of feed text, applied-row rendering,
and the inline mark-applied control.

Run: python test_dashboard.py
"""

from datetime import datetime, timedelta, timezone

import store
from dashboard import APPLIED_ROUTE, _build_html, render, score_job

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
def job_at(days_ago: int, **kw) -> dict:
    published = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(store.UTC_FMT)
    return {"title": "", "summary": "", "location": "", "published": published, **kw}

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
def full_job(job_id: str, days_ago: int, title: str = "") -> dict:
    return {**job_at(days_ago, title=title), "id": job_id, "company": "", "source": "",
            "link": f"https://example.com/{job_id}", "status": "new"}

store.load_jobs = lambda: [
    full_job("lo_old", 18),
    full_job("hi", 20, title="Data Analyst"),
    full_job("lo_new", 16),
]
page = render()
assert page.index("data-id='hi'") < page.index("data-id='lo_new'") < page.index("data-id='lo_old'")

print("OK: test_dashboard passed")
