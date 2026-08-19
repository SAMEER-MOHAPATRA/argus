# Argus — Domain Glossary

## Domain

**Discovery** — RSS feed ingestion, relevance filtering, and deduplication of job listings. Produces `Job` records. All feed-derived text is sanitized to plain text before storage (`sanitize_html`). Entry point: `discover.py` (`--check` for feed health).

**Tracking** — Recording where each `Job` stands. A single `status` column on the job row is the state machine; the dashboard's "✓ Applied" button advances it and the Recent Applications panel reports it. No separate entry point.

**Dashboard** — Serves the report and owns the write endpoint. Interface: `render() -> str` builds the page from the store; `serve()` runs it on port 8765 and renders fresh per request, so there is no `dashboard.html` artifact to go stale. `APPLIED_ROUTE` and the `Handler` that serves it live in the same module as the JS that calls it. Entry point: `dashboard.py`.

## Core entities

- **Job** — A discovered listing with fields: id, title, company, location, source, link, published, status, status_date, summary.
- **Application** — A `Job` whose status moved past `new`. Status is one of: new, applied, interview, rejected. `status_date` records the last change. There is no separate applications file.

## Architecture

- **store.py** — plain module functions (`load_jobs`, `add_jobs`, `get_status`, `set_status`, `this_week`) that own the CSV schema and date formats. `dashboard.py` HTML-escapes at render.
- **config.toml + config.py** — All configuration (feeds, role keywords, seniority blocklist) in `config.toml`. `config.py` loads it once at import and exports typed constants.
