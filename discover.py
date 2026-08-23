"""
discover.py — scrapes DA/BA/analytics jobs from RSS feeds.
Adds new listings to jobs_found.csv; skips anything already seen.

Usage:
    python discover.py
    python discover.py --days 14
    python discover.py --days 7 --verbose
    python discover.py --check   # feed health check, no writes
"""

import argparse
import hashlib
import logging
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

# pyrefly: ignore [missing-import]
import feedparser

import store
from config import FEEDS, MAX_PER_FEED, ROLE_KEYWORDS, SENIORITY_BLOCK

# ─── Configuration ───────────────────────────────────────────────────────

DEFAULT_DAYS = 7

# ponytail: 8s socket timeout prevents feedparser from hanging on dead hosts
socket.setdefaulttimeout(8)

SUMMARY_PATH = Path("logs/last_run_summary.txt")

log = logging.getLogger("discover")


# ─── Logging ─────────────────────────────────────────────────────────────


def setup_logging(verbose: bool = False) -> None:
    # Windows cp1252 console fix lives in store.py (imported by all scripts)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        stream=sys.stdout,
        force=True,
    )


# ─── CSV Utilities ───────────────────────────────────────────────────────


def load_seen_ids() -> set[str]:
    seen: set[str] = set()
    for row in store.load_jobs():
        seen.update(filter(None, [row.get("id"), row.get("link")]))
    log.info("Loaded %d seen IDs from store", len(seen))
    return seen


# ─── Feed Fetching ───────────────────────────────────────────────────────


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch and parse an RSS feed. No retries: the daily run is the retry."""
    feed = feedparser.parse(url)
    # ponytail: bozo=1 with entries is fine (Himalayas does this)
    if feed.bozo and not feed.entries:
        log.warning(
            "Feed fetch failed for %s: %s",
            url, getattr(feed, "bozo_exception", "unknown error"),
        )
    return feed


# ─── Entry Parsing ───────────────────────────────────────────────────────


def parse_published(entry) -> datetime:
    """Extract publication date from an RSS entry."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError) as exc:
                log.debug("Failed to parse date field '%s': %s", field, exc)
    log.debug(
        "No valid date found for entry '%s', using current time",
        getattr(entry, "title", "unknown"),
    )
    return datetime.now(timezone.utc)


def extract_job_id(url: str) -> str:
    """Generate a stable unique ID from a job URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    tail = path.split("/")[-1] if path else ""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", tail)

    if len(slug) < 4:
        # ponytail: short slugs risk collisions — hash instead
        slug = hashlib.md5(url.encode()).hexdigest()[:12]

    return slug


def extract_location(entry, source_label: str) -> str:
    """Extract location from an RSS entry with source-aware fallbacks."""
    loc = getattr(entry, "location", None)
    if loc and str(loc).strip():
        return str(loc).strip()

    tags = getattr(entry, "tags", [])
    for tag in tags:
        term = getattr(tag, "term", "")
        if term and any(
            kw in term.lower()
            for kw in ("remote", "usa", "europe", "worldwide", "india")
        ):
            return term

    source_lower = source_label.lower()
    if any(x in source_lower for x in ("remoteok", "wwr", "weworkremotely", "himalayas")):
        return "Remote"

    return "Not specified"


# ─── Feed Processing ────────────────────────────────────────────────────


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_html(text: str) -> str:
    """Strip HTML tags and decode entities. Feed text is not trusted."""
    clean = _HTML_TAG_RE.sub(" ", text)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def process_feed(
    label: str, url: str, days: int, seen: set[str],
) -> tuple[list[dict], str | None]:
    """Process a single RSS feed and return new job listings.

    seen is read-only: feeds run in parallel, so cross-feed dedup happens
    once after the join (see main).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results: list[dict] = []

    try:
        feed = fetch_feed(url)

        if not feed.entries:
            log.info("Feed '%s' returned 0 entries", label)
            return results, None

        for entry in feed.entries[:MAX_PER_FEED]:
            pub_date = parse_published(entry)

            if pub_date < cutoff:
                continue

            link = getattr(entry, "link", "")
            if not link:
                continue

            job_id = extract_job_id(link)
            if job_id in seen or link in seen:
                continue

            # sanitize everything feed-controlled — the store holds plain text
            title = sanitize_html(getattr(entry, "title", ""))
            company = sanitize_html(getattr(entry, "author", "")) or "Unknown"
            description = sanitize_html(getattr(entry, "summary", ""))

            title_lower = title.lower()
            combined_lower = title_lower + " " + description.lower()

            # relevance: matches a role keyword and isn't too senior
            if not any(kw in combined_lower for kw in ROLE_KEYWORDS) or any(
                flag in title_lower for flag in SENIORITY_BLOCK
            ):
                continue

            results.append({
                "id":          job_id,
                "title":       title,
                "company":     company,
                "location":    extract_location(entry, label),
                "source":      label,
                "link":        link,
                "published":   pub_date.strftime(store.UTC_FMT),
                "status":      "new",
                "status_date": "",
                "summary":     description,
            })

        log.info(
            "Feed '%s': %d new jobs from %d entries",
            label, len(results), min(len(feed.entries), MAX_PER_FEED),
        )

    except Exception as exc:
        log.error("Feed '%s' failed: %s", label, exc)
        return results, str(exc)

    return results, None


# ─── Summary ─────────────────────────────────────────────────────────────


def write_summary(feed_stats: list[tuple], all_jobs: list[dict], days: int) -> None:
    """Print summary to terminal and save to logs/last_run_summary.txt."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"[{ts}]  Job Discovery  |  window: last {days} days",
        "-" * 55,
    ]

    for label, found, error in feed_stats:
        if error:
            lines.append(f"  {label:<35} ERROR: {error}")
        else:
            lines.append(f"  {label:<35} {found:>4} new")

    lines.append("-" * 55)

    if all_jobs:
        top = all_jobs[0]
        lines.append(f"  ✅ {len(all_jobs)} new jobs → jobs_found.csv")
        lines.append(
            f"  🔝 Top match: {top['title']} @ {top['company']}"
        )
    else:
        lines.append("  🔎 No new jobs found this run.")

    lines.append("")
    summary = "\n".join(lines)

    print(summary)

    # Save to file for later review (scheduled runs)
    SUMMARY_PATH.parent.mkdir(exist_ok=True)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    log.debug("Summary written to %s", SUMMARY_PATH)


# ─── Main ────────────────────────────────────────────────────────────────


def check_feeds() -> None:
    """Print feed health without touching the store."""
    for f in FEEDS:
        feed = fetch_feed(f["url"])
        sample = feed.entries[0].title[:60] if feed.entries else "N/A"
        print(f"{f['label']:30s} | {len(feed.entries):>3} entries | bozo={feed.bozo} | {sample}")


def main(days: int, verbose: bool = False) -> None:
    setup_logging(verbose)
    log.info("Starting job discovery (window: %d days)", days)
    seen = load_seen_ids()
    all_jobs: list[dict] = []
    feed_stats: list[tuple] = []

    # threads, not processes: feed work is socket wait. map keeps FEEDS order.
    with ThreadPoolExecutor(max_workers=8) as pool:
        per_feed = list(pool.map(
            lambda f: process_feed(f["label"], f["url"], days, seen), FEEDS,
        ))

    # dedup once, in FEEDS order — same result as the old sequential run
    for f, (jobs, error) in zip(FEEDS, per_feed):
        kept = []
        for job in jobs:
            if job["id"] in seen or job["link"] in seen:
                continue
            seen.update([job["id"], job["link"]])
            kept.append(job)
        all_jobs.extend(kept)
        feed_stats.append((f["label"], len(kept), error))

    all_jobs.sort(key=lambda x: x["published"], reverse=True)

    if all_jobs:
        store.add_jobs(all_jobs)
        log.info("Added %d new jobs", len(all_jobs))

    write_summary(feed_stats, all_jobs, days)
    log.info("Job discovery complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DA/BA job discovery via RSS")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--check", action="store_true", help="Feed health check, no writes")
    args = parser.parse_args()
    if args.check:
        check_feeds()
    else:
        main(days=args.days, verbose=args.verbose)
