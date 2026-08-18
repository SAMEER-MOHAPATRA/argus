import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

# ponytail: every script imports store — fix Windows cp1252 console once here
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]

# ponytail: these module globals ARE the persistence seam — tests reassign
# them to a tmp dir (see test_store.py); no protocol/adapters needed
CSV_PATH = Path("jobs_found.csv")
APPLIED_PATH = Path("jobs_applied.csv")
PREP_PATH = Path("application_prep.csv")

UTC_FMT = "%Y-%m-%d %H:%M UTC"
DATE_FMT = "%Y-%m-%d"

JOBS_FIELDS = [
    "id", "title", "company", "location", "source",
    "link", "published", "applied", "summary",
]

APPLIED_FIELDS = ["job_id", "title", "company", "date_applied", "result", "notes"]

PREP_FIELDS = [
    "job_id", "title", "company", "link",
    "tailored_bullets", "missing_keywords", "cover_snippet",
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_html(text: str) -> str:
    """Strip HTML tags and decode entities.

    Lives here, not in discover: everything imports store, so prep can reuse
    it without dragging in feedparser.
    """
    clean = _HTML_TAG_RE.sub(" ", text)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _load(path: Path) -> list[dict]:
    try:
        # utf-8-sig: hand-edited CSVs (Excel) often carry a BOM that would
        # otherwise corrupt the first fieldname
        with open(path, "r", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def load_jobs() -> list[dict]:
    return _load(CSV_PATH)


def load_applications() -> list[dict]:
    return _load(APPLIED_PATH)


def _save(path: Path, fields: list[str], rows: list[dict]) -> None:
    # ponytail: rewrite the whole file so the header always matches the
    # schema — appending under a stale header silently misaligns columns
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def add_jobs(jobs: list[dict]) -> None:
    _save(CSV_PATH, JOBS_FIELDS, load_jobs() + jobs)


def mark_applied(job_id: str) -> bool:
    """Flag a job as applied in jobs_found.csv and log it to jobs_applied.csv."""
    jobs = load_jobs()
    job = next((j for j in jobs if j.get("id") == job_id), None)
    if job is None:
        return False
    job["applied"] = "yes"
    _save(CSV_PATH, JOBS_FIELDS, jobs)
    apps = load_applications()
    apps.append({
        "job_id": job_id,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "date_applied": datetime.now(timezone.utc).strftime(DATE_FMT),
        "result": "Applied",
        "notes": "",
    })
    _save(APPLIED_PATH, APPLIED_FIELDS, apps)
    return True


def save_prep_results(rows: list[dict]) -> None:
    _save(PREP_PATH, PREP_FIELDS, rows)


def upsert_prep(row: dict) -> None:
    """Replace (or append) the prep row for row['job_id']."""
    rows = [r for r in _load(PREP_PATH) if r.get("job_id") != row["job_id"]]
    _save(PREP_PATH, PREP_FIELDS, rows + [row])


def this_week(rows: list[dict], key: str, fmt: str = DATE_FMT, days: int = 7) -> list[dict]:
    """Filter already-loaded rows to those dated within the last `days`."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [r for r in rows if parse_date(r.get(key, ""), fmt) > cutoff]


def parse_date(date_str: str, fmt: str) -> datetime:
    """Parse a stored date; unparseable strings sort as oldest-possible."""
    try:
        return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)
