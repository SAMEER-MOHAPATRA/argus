# Argus

Python pipeline that discovers, scores, and tracks job applications end-to-end.

Named for Argus Panoptes, the hundred-eyed watchman — it watches the feeds so you do not have to.

## What it does

- **Discover** — scrapes job listings from RSS feeds (WeWorkRemotely, RemoteOK, and more via `config.toml`), filters by role keywords and seniority, dedupes with content hashing → `jobs_found.csv`
- **Prep** — keyword-gap analysis between each job description and your master resume; generates tailored resume bullets and cover-letter snippets → `application_prep.csv`
- **Dashboard** — local web dashboard ranking jobs by match score, with one-click apply and mark-applied, plus a recent-applications panel

## Usage

```bash
pip install -r requirements.txt
python discover.py --days 7    # find new jobs
python prep.py                 # tailor materials (needs master_resume.txt)
python dashboard.py            # serve the dashboard at localhost:8765
```

Create a `master_resume.txt` with your resume text — `prep.py` matches job keywords against it. Personal data files (`master_resume.txt`, `jobs_*.csv`) are gitignored.

## Configuration

Everything lives in `config.toml`: feeds, role keywords, seniority blocklist, bullet library, cover-letter template.

## Automation

`.github/workflows/discover.yml` runs discovery daily; `refresh.bat` runs the full local pipeline.
