# Argus — Explained

Notes that explain how Argus works, one topic at a time.

Each file answers one question. We add files as questions come up. When the set
covers enough, we merge the best parts into the top-level `README.md`.

## Written

| # | Topic | Answers |
|---|---|---|
| 01 | [Feeds and where jobs come from](01-feeds-and-data-sources.md) | What RSS is, how Google News becomes a feed, why LinkedIn and Naukri links are redirects |

## Queue

Open questions, not yet written. Take them in any order.

| Topic | The question to answer | Where the code is |
|---|---|---|
| The store | How does `jobs_found.csv` work as a database? Why CSV and not SQLite? Where do schema and date formats live? | `store.py` |
| The dashboard | How does the page get built and served? How does the "✓ Applied" button write back to the store? | `dashboard.py` |
| Deduplication | How does Argus know it has seen a job before? Why does `extract_job_id` hash short slugs instead of using them? | `discover.py` — `extract_job_id`, `load_seen_ids` |
| Concurrency | Why do feeds run in threads and not processes? Why does dedup happen after the join and not inside each worker? | `discover.py` — `main`, `process_feed` |
| Configuration | Why is config split across `config.toml` and `config.py`? What belongs in each? | `config.toml`, `config.py` |
| Status tracking | What are the job states and what moves a job between them? Why is one column the whole state machine? | `store.py` — `get_status`, `set_status` |
| Trust and sanitizing | Why is all feed text stripped to plain text before storage, and why does the dashboard escape again at render? | `discover.py` — `sanitize_html`; `dashboard.py` |
| Scheduled runs | How does a daily run work, and where does its output go? | `refresh.bat`, `logs/last_run_summary.txt` |

## Generated

| File | What it is | Caveats |
|---|---|---|
| [callflow.html](callflow.html) | Call-flow and architecture diagrams built by `graphify` from the AST. 8 Mermaid diagrams, 7 call tables. Open it in a browser. | Regenerate after code changes, or it goes stale. Sections 2-5 carry graphify's generic template names, not names derived from Argus. Needs an internet connection: Mermaid loads from a CDN. |

Rebuild it with:

```
graphify extract . --code-only --out .
graphify cluster-only .
graphify export callflow-html --graph graphify-out/graph.json --output docs/explained/callflow.html
```

`graphify-out/` is git-ignored. It holds the graph and its AST cache.

## Conventions

- One topic per file. Number the files so the order is clear.
- Show real output, not invented examples. Verify a claim before writing it.
- Name the limits of a design, not only its benefits.
- Move a row from **Queue** to **Written** when its file exists.
