# job_tracker — Domain Glossary

## Domain

**Discovery** — RSS feed ingestion, relevance filtering, and deduplication of job listings. Produces `Job` records. Entry point: `discover.py` (`--check` for feed health).

**Preparation** — Cover-letter tailoring for a `Job` by extracting keywords from its description and matching them against a bullet library. Produces `PrepResult` records. Interface: `prep_one(job)` preps a single job on demand (fetches the live JD from the job link, falling back to the stored summary) and upserts `application_prep.csv`; batch `main()` preps all jobs from stored summaries only. In served mode, clicking Apply on the dashboard routes through `/prep/<id>`, which runs `prep_one` and shows the materials before linking to the posting. Entry point: `prep.py`.

**Tracking** — Logging applications and generating weekly reviews. Produces `Application` records. Entry point: `review.py`.

**Dashboard** — Read-only HTML report aggregating `Job` and `Application` data. Interface: `render() -> str` (serve.py serves it live, never writing to disk); `main()` writes `dashboard.html` for the CLI/refresh.bat path only, so the file may be stale while the server runs. Entry point: `dashboard.py`. The serve-mode route contract (`PREP_ROUTE`, `APPLIED_ROUTE`) is defined once in `dashboard.py`; both the emitted JS and `serve.py`'s routing import it.

## Core entities

- **Job** — A discovered listing with fields: id, title, company, location, source, link, published, status, status_date, summary.
- **Application** — A `Job` whose status moved past `new`. Status is one of: new, applied, interview, rejected. `status_date` records the last change. There is no separate applications file.
- **PrepResult** — Tailored cover-letter materials with fields: job_id, title, company, link, tailored_bullets, missing_keywords, cover_snippet.

## Architecture

- **store.py** — plain module functions (`load_jobs`, `add_jobs`, `get_status`, `set_status`, `save_prep_results`, `this_week`) that own the CSV schemas and date formats. All feed-derived text is sanitized to plain text before storage; `dashboard.py` additionally HTML-escapes at render.
- **config.toml + config.py** — All configuration (feeds, keywords, bullet map, cover template) in `config.toml`. `config.py` loads it once at import and exports typed constants. `KEYWORD_PATTERN` is generated from `BULLET_MAP` keys to prevent drift.
