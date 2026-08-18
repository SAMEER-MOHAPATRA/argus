# job_tracker — Domain Glossary

## Domain

**Discovery** — RSS feed ingestion, relevance filtering, and deduplication of job listings. Produces `Job` records. Entry point: `discover.py` (`--check` for feed health).

**Preparation** — Cover-letter tailoring for a `Job` by extracting keywords from its description and matching them against a bullet library. Produces `PrepResult` records. Interface: `prep_one(job)` preps a single job on demand (fetches the live JD from the job link, falling back to the stored summary) and upserts `application_prep.csv`; batch `main()` preps all jobs from stored summaries only. In served mode, clicking Apply on the dashboard routes through `/prep/<id>`, which runs `prep_one` and shows the materials before linking to the posting. Entry point: `prep.py`.

**Tracking** — Recording where each `Job` stands. A single `status` column on the job row is the state machine; the dashboard's "✓ Applied" button advances it and the Recent Applications panel reports it. No separate entry point.

**Dashboard** — Serves the report and owns the write endpoint. Interface: `render() -> str` builds the page from the store; `serve()` runs it on port 8765 and renders fresh per request, so there is no `dashboard.html` artifact to go stale. Routes (`PREP_ROUTE`, `APPLIED_ROUTE`) and the `Handler` that serves them live in the same module as the JS that calls them. Entry point: `dashboard.py`.

## Core entities

- **Job** — A discovered listing with fields: id, title, company, location, source, link, published, status, status_date, summary.
- **Application** — A `Job` whose status moved past `new`. Status is one of: new, applied, interview, rejected. `status_date` records the last change. There is no separate applications file.
- **PrepResult** — Tailored cover-letter materials with fields: job_id, title, company, link, tailored_bullets, missing_keywords, cover_snippet.

## Architecture

- **store.py** — plain module functions (`load_jobs`, `add_jobs`, `get_status`, `set_status`, `save_prep_results`, `this_week`) that own the CSV schemas and date formats. All feed-derived text is sanitized to plain text before storage; `dashboard.py` additionally HTML-escapes at render.
- **config.toml + config.py** — All configuration (feeds, keywords, bullet map, cover template) in `config.toml`. `config.py` loads it once at import and exports typed constants. `KEYWORD_PATTERN` is generated from `BULLET_MAP` keys to prevent drift.
