# ADR-0001: Introduce a persistence seam via store.py

**Status:** Accepted (amended 2026-07-03 — see below)  
**Date:** 2026-07-02  
**Deciders:** User + agent

## Context

The codebase has three modules (`job_discovery.py`, `application_prep.py`, `weekly_review.py`) that each read/write CSV files directly. The CSV schema (`id`, `title`, `company`, etc.) is only defined once in `job_discovery.py`; the other modules trust the file headers implicitly. There is no single seam for data access, making tests dependent on real CSV files on disk and schema changes requiring edits in multiple files.

During the architecture review (2026-07-02) this was identified as Candidate 2 — the top recommendation, because fixing it pays back across every other module.

## Decision

Introduce a `store.py` module that defines a `JobStore` protocol (interface) with two adapters:

- **`CsvJobStore`** — production adapter wrapping CSV read/write
- **`InMemoryJobStore`** — test adapter backed by an in-memory list/dict

The store exposes:
- `load_jobs()` / `load_jobs_this_week(days)` / `load_jobs_for_feed(label)`
- `append_jobs(jobs)` / `job_exists(id_or_link)`
- `load_applications()` / `load_applications_this_week(days)`
- `save_applications(apps)` / `save_prep_results(rows)`

The CSV schema gains a `summary` field to carry the job description from Discovery through to Preparation (previously the description was parsed for filtering but discarded before storage).

## Consequences

**Positive:**
- Schema changes are local to `store.py`
- Switching storage format (JSON, SQLite) means changing one adapter
- Tests use `InMemoryJobStore` — no disk I/O, deterministic, fast
- Downstream modules (`application_prep.py`, `weekly_review.py`) stop knowing about CSV

**Negative:**
- One extra file to maintain (`store.py` + adapters)
- `CsvJobStore` is slightly more code than the current inline CSV logic, but the duplication across three modules was already higher

## Alternatives considered

- **Keep inline CSV** — rejected because the duplication already caused drift (different error handling, different field lists). The deletion test confirmed CSV logic is pure pass-through.
- **SQLite** — rejected for now. CSV remains human-readable and the schema is simple. `store.py` makes a future switch to SQLite an adapter change.

## Amendment (2026-07-03)

As implemented, `store.py` is plain module functions, not a `JobStore` protocol with
`CsvJobStore`/`InMemoryJobStore` adapters. One adapter means a hypothetical seam — nothing
varied, so the protocol was skipped. The seam is the module-global paths
(`CSV_PATH`, `APPLIED_PATH`, `PREP_PATH`), which are resolved at call time: tests
(`test_store.py`) reassign them to a tmp dir, delivering this ADR's testability goal
(no disk I/O in the real cwd, deterministic) without the adapter machinery. A future
storage switch remains a `store.py`-local change.
