# Job Tracker — Simplify, Speed Up, Unify Tracking

## Context

`job_tracker` is a lean (~1,165 LOC) personal RSS job-discovery + application tool: 7 Python
modules + 3 test files, backed by CSVs. The code is already well-written (ponytail-style), so this
is **consolidation and polish**, not a rewrite. Goals: fewer files, faster discovery, friendlier UX.

Cross-checked against four peer repos: **JobFunnel** (mature, archived) independently landed on the
same "CSV-as-source-of-truth + RSS-friendly" shape and contributes the transferable ideas below;
**career-ops** (~150 `.mjs` scripts) is the cautionary bloat anti-pattern; **oxylabs google-jobs**
and **ai-job-search** confirm our RSS approach beats Selenium and that a one-verb-per-command UX is
worth having. Deliberately **not** adopting: sklearn/TF-IDF, Selenium, pydantic, LLM fit-eval — all
add dependencies for marginal gain at this size.

Decisions confirmed with user: full consolidation (5 modules + 1 CLI), adopt a single `status`
column as the tracking state machine, serve-only (drop the `dashboard.html` artifact), and add
parallel fetch + content dedup + inline mark-applied. (Block list declined.)

## Target file layout

`config.py`, `discover.py`, `prep.py`, `store.py`, `dashboard.py` (absorbs `serve.py` + `review.py`),
and a thin `jobs.py` dispatcher. **Deleted:** `serve.py`, `review.py`, `test_prep.py` stays,
`refresh.bat` retargeted. **Removed artifact:** `dashboard.html` write path.

---

## 1. `store.py` — unify tracking on a `status` column, host `sanitize_html`

- Replace the `applied` column in `JOBS_FIELDS` with `status` + `status_date`. Values: `new`
  (default/empty), `applied`, `interview`, `rejected`.
- Delete `APPLIED_PATH`, `APPLIED_FIELDS`, `load_applications`, and drop `jobs_applied.csv`.
- Replace `mark_applied(job_id)` with `set_status(job_id, status)` → sets `status`, stamps
  `status_date` (UTC `DATE_FMT`), rewrites `jobs_found.csv`, returns bool.
- Move `sanitize_html` (currently `discover.py:43`) here — `store` is imported by everyone, breaking
  the `prep → discover` import (prep no longer drags in feedparser). Keep the `_HTML_TAG_RE`.
- Add `dedupe(jobs, existing)` helper: drop a candidate whose normalized `title|company` already
  exists (cheap `str.lower().strip()` key set — no sklearn). Used by discovery.
- **Migration** (one-off, in the implementation): rewrite `jobs_found.csv` mapping
  `applied=="yes"` → `status="applied"`, `status_date=""` (unknown); the single historic applied
  row (`data-analyst`, 2026-07-03 in `jobs_applied.csv`) gets `status_date=2026-07-03`.

## 2. `discover.py` — parallel fetch + content dedup

- `from store import sanitize_html` (remove local copy).
- Parallelise the feed loop (`discover.py:275`, already flagged in its own ponytail note) with
  `concurrent.futures.ThreadPoolExecutor(max_workers=8)` over `process_feed`. `seen` mutation moves
  out of the worker: each worker returns its jobs, and dedup (id/link **and** the new
  `store.dedupe` title|company pass) happens once after join, preserving determinism. Keep the 8s
  socket timeout.
- `load_seen_ids` reads only `store.load_jobs()` now (no applications file).

## 3. `prep.py` — decouple from discover

- `from store import sanitize_html`. No behavior change otherwise. Consider (optional, low-risk)
  rendering prep from the stored summary immediately and skipping the blocking live fetch — leave
  as-is unless we want it; flagged, not scheduled.

## 4. `dashboard.py` — absorb serve + review, serve-only, inline mark-applied

- Move `serve.py`'s `Handler`, `_already_running`, and `PORT` into `dashboard.py`; keep
  `PREP_ROUTE`/`APPLIED_ROUTE` (now same-module, drop the cross-import comment). Add a `serve()`
  entry function.
- Delete `main()`'s `dashboard.html` write path and `DASHBOARD_PATH`; render is live-only.
- Fold `review.py`'s weekly-review aggregation into the dashboard as a **Recent applications**
  panel (status != `new`, most recent `status_date` first) + the existing week counts. Drop
  `review.py`.
- Replace the `localStorage` + `confirm()`-on-revisit flow (`dashboard.py:203-243`) with a per-row
  **inline status control**: an "✓ Applied" button POSTing to `APPLIED_ROUTE` and reloading. The
  POST handler calls `store.set_status(id, "applied")`.
- `render()`/`score_job` read `status` instead of `applied`; "done" row styling keys on
  `status != "new"`.

## 5. `jobs.py` — single entry point (NEW, ~15 lines)

- `python jobs.py discover [--days N] [--check]` → `discover.main`/`check_feeds`
- `python jobs.py serve` → `dashboard.serve`
- `python jobs.py refresh` → discover (default 3 days) then serve
- Retarget `refresh.bat` to call `python jobs.py refresh`.

## 6. Tests

- `test_store.py`: swap `mark_applied`/`load_applications`/`APPLIED_PATH` assertions for
  `set_status` + `status`/`status_date`; add a `dedupe` case; add a `sanitize_html` case (moved here).
- `test_dashboard.py`: replace `applied`/`APPLIED_ROUTE`-JS assertions with the inline-button markup
  and `status`-based "done" styling; `score_job` cases unchanged (scoring logic untouched).
- `test_prep.py`: update the `sanitize_html` import source (`store`, not `discover`) if referenced.
- Update `CONTEXT.md`: Job entity `applied → status/status_date`, drop Application entity &
  `jobs_applied.csv`, note `sanitize_html` now lives in `store`, dashboard is serve-only.

---

## Implementation order

Tests must stay green after each step (`python test_store.py && python test_dashboard.py &&
python test_prep.py` → all print `OK`).

1. Parallel fetch in `discover.py` (isolated, ship first).
2. Move `sanitize_html` → `store.py`; decouple `prep.py` from `discover.py`.
3. `status` column + migration of the 102 rows in `jobs_found.csv` (one historic applied row:
   `data-analyst`, status_date `2026-07-03`); `mark_applied` → `set_status`.
4. `dashboard.py` absorbs `serve.py` + `review.py`, serve-only, inline "✓ Applied" button.
5. `jobs.py` dispatcher + retarget `refresh.bat`.
6. Content dedup (title|company key).
7. Update `test_store.py`, `test_dashboard.py`, `test_prep.py`, `CONTEXT.md`.

## Verification

1. `python test_store.py && python test_dashboard.py && python test_prep.py` — all print `OK`.
2. `python jobs.py discover --check` — feed health prints, no writes.
3. `python jobs.py discover --days 3` — confirm parallel fetch is faster (wall-clock ~ one feed,
   not N); confirm no duplicate title|company rows added.
4. `python jobs.py serve` — dashboard renders; click "✓ Applied" on a row → row greys out, Recent
   applications panel updates, `jobs_found.csv` shows `status=applied` + today's `status_date`.
5. `git status` — `serve.py`, `review.py`, `jobs_applied.csv`, `dashboard.html` gone; `jobs.py` new.

## Notes / risks

- The `status` schema change is the one non-surgical step (touches store, discover, dashboard,
  tests, both CSVs) — done as one focused commit with the CSV migration, per karpathy "surface the
  ripple, don't sprawl."
- Sequence: (a) parallel fetch — isolated, ship first; (b) `sanitize_html` move + prep decouple;
  (c) status-column migration + tracking unify; (d) dashboard absorb serve/review + inline button;
  (e) `jobs.py` + refresh.bat. Keep tests green after each.
- Windows/PowerShell environment; the console-encoding fix already lives in `store.py` — don't
  reintroduce a second one elsewhere.
- Peer-repo research (JobFunnel, ai-job-search, oxylabs google-jobs, career-ops) is already folded
  into the Context section above; no need to re-clone unless verifying a specific detail.

## Suggested skills for whoever implements this

- `karpathy-guidelines` — keep changes surgical, one focused commit per step above.
- `tdd` or `implement` — drive the build; keep the three test files green after each step.
- `code-review` — run after implementation, before merging (Standards + Spec axes).
- `improve-codebase-architecture` — already run once to produce this plan; only re-invoke if the
  design is reopened.
