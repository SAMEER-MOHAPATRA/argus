"""Checks on the persistence seam: round-trip, set_status, upsert, week cutoff,
plus sanitize_html (moved here from discover so prep need not import feedparser).

Run: python test_store.py
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import store

# the module-global paths are the seam: point them at a tmp dir
_tmp = Path(tempfile.mkdtemp())
store.CSV_PATH = _tmp / "jobs.csv"
store.PREP_PATH = _tmp / "prep.csv"

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

# upsert_prep replaces by job_id, appends new ids
PREP = {"job_id": "j1", "title": "old", "company": "", "link": "",
        "tailored_bullets": "", "missing_keywords": "", "cover_snippet": ""}
store.upsert_prep(PREP)
store.upsert_prep({**PREP, "title": "new"})
store.upsert_prep({**PREP, "job_id": "j2", "title": "other"})
prep_rows = store._load(store.PREP_PATH)
assert [(r["job_id"], r["title"]) for r in prep_rows] == [("j1", "new"), ("j2", "other")]

# this_week keeps recent rows; garbage dates sort as oldest-possible
rows = [
    {"d": (now - timedelta(days=1)).strftime(store.DATE_FMT)},
    {"d": (now - timedelta(days=10)).strftime(store.DATE_FMT)},
    {"d": "garbage"},
]
assert store.this_week(rows, "d") == [rows[0]]
assert store.parse_date("garbage", store.DATE_FMT) == datetime.min.replace(tzinfo=timezone.utc)

# sanitize_html strips tags, decodes entities, collapses whitespace
assert store.sanitize_html("<p>Data &amp;  Analyst</p>") == "Data & Analyst"
assert store.sanitize_html("<br/>Remote\n\n  (EU)") == "Remote (EU)"
assert store.sanitize_html("") == ""

print("OK: test_store passed")
