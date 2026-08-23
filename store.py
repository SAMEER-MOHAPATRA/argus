import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ponytail: every script imports store — fix Windows cp1252 console once here
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]

# ponytail: this module global IS the persistence seam — tests reassign
# it to a tmp dir (see tests.py); no protocol/adapters needed
CSV_PATH = Path("jobs_found.csv")

UTC_FMT = "%Y-%m-%d %H:%M UTC"
DATE_FMT = "%Y-%m-%d"

JOBS_FIELDS = [
    "id", "title", "company", "location", "source",
    "link", "published", "status", "status_date", "summary",
]

# the whole application lifecycle — one column, no second file
STATUSES = ("new", "applied", "interview", "rejected")

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


def get_status(job: dict) -> str:
    """Status of a job row. Blank or missing reads as 'new'."""
    return (job.get("status") or "").strip().lower() or "new"


def _save(rows: list[dict]) -> None:
    # ponytail: rewrite the whole file so the header always matches the
    # schema — appending under a stale header silently misaligns columns
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOBS_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def add_jobs(jobs: list[dict]) -> None:
    _save(load_jobs() + jobs)


def set_status(job_id: str, status: str) -> bool:
    """Set a job's status and stamp status_date. False if id or status is unknown."""
    if status not in STATUSES:
        return False
    jobs = load_jobs()
    job = next((j for j in jobs if j.get("id") == job_id), None)
    if job is None:
        return False
    job["status"] = status
    job["status_date"] = datetime.now(timezone.utc).strftime(DATE_FMT)
    _save(jobs)
    return True


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
