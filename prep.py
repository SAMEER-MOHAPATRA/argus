import re
import urllib.request
from collections import Counter

import store
from config import BULLET_MAP, COVER_TEMPLATE, DEFAULTS, KEYWORD_PATTERN
from store import sanitize_html

_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def load_master_resume() -> str:
    # Rocky note: read once, lowercase once — that's it.
    with open("master_resume.txt", "r", encoding="utf-8") as f:
        return f.read().lower()


def build_bullets(master_resume: str, jd_text: str) -> tuple[list[str], list[str]]:
    # rank JD keywords by frequency (ties keep first-seen order), pick their bullets
    counts = Counter(m.group(1).lower() for m in KEYWORD_PATTERN.finditer(jd_text))
    ranked = [kw for kw, _ in counts.most_common()]
    missing = [kw for kw in ranked if kw not in master_resume]
    bullets = list(dict.fromkeys(BULLET_MAP[kw] for kw in ranked))[:len(DEFAULTS)]
    # pad with defaults — the cover template has exactly len(DEFAULTS) slots
    bullets += DEFAULTS[len(bullets):]
    return bullets, missing


def build_cover(job: dict, bullets: list[str]) -> str:
    return COVER_TEMPLATE.format(
        title=job["title"],
        company=job["company"],
        b0=bullets[0],
        b1=bullets[1],
        b2=bullets[2],
    )


def fetch_jd(link: str) -> str:
    """Fetch the live job posting and reduce it to plain text."""
    req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return sanitize_html(_SCRIPT_RE.sub(" ", html))


def prep_one(job: dict, fetch=fetch_jd) -> dict:
    """Prep a single job on demand: live JD when reachable, stored summary otherwise."""
    try:
        jd = fetch(job["link"])
    except Exception:
        jd = ""
    # a thin fetch (login wall, JS-only page) carries less signal than the RSS summary
    if len(jd) < len(job.get("summary", "")):
        jd = None
    row = prep_job(job, load_master_resume(), jd)
    store.upsert_prep(row)
    return row


def prep_job(job: dict, master_resume: str, jd_text: str | None = None) -> dict:
    # store fields are already sanitized plain text at discovery time
    if jd_text is None:
        jd_text = job.get("summary", "")
    bullets, missing = build_bullets(
        master_resume, f"{job['title']} {job['company']} {jd_text}"
    )
    return {
        "job_id":           job["id"],
        "title":            job["title"],
        "company":          job["company"],
        "link":             job["link"],
        "tailored_bullets": " | ".join(bullets),
        "missing_keywords": ", ".join(missing),
        "cover_snippet":    build_cover(job, bullets),
    }


def main() -> None:
    master_resume = load_master_resume()
    jobs = store.load_jobs()

    if not jobs:
        print("❌ Run discover.py first to create jobs_found.csv")
        return

    prepped = [prep_job(job, master_resume) for job in jobs]
    store.save_prep_results(prepped)
    print(f"✅ Prepared materials for {len(prepped)} jobs → application_prep.csv")


if __name__ == "__main__":
    main()
