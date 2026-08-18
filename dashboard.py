"""
dashboard.py — generates a local HTML dashboard from the store.

Usage:
    python dashboard.py
    python dashboard.py --open   # auto-open in browser
"""

import argparse
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import store

DASHBOARD_PATH = Path("dashboard.html")

# route contract with serve.py — the emitted JS and the server routing both
# use these, so a rename lands in one place
PREP_ROUTE = "/prep/"
APPLIED_ROUTE = "/applied/"

# coffee palette: espresso text, mocha accent, caramel highlight, latte muted, cream bg
_PALETTE = """:root {
  --espresso: #3b2a20; --mocha: #6f4e37; --caramel: #b57b3f;
  --latte: #9c8672; --cream: #f6f0e7; --card: #fffbf4; --line: #e7dccb;
}"""

# ---- points system (from resume: DA/AE profile, remote-first) ----
# title: Data Analyst ranks highest, other target roles below
TITLE_POINTS = [
    ("data analyst", 30),
    ("business analyst", 20),
    ("analytics engineer", 20),
]
# location: remote first, then India
LOCATION_POINTS = [
    ("remote", 20), ("work from anywhere", 20), ("anywhere", 20),
    ("india", 10),
]
# skills pulled from resume — +5 each, found in title or summary
SKILL_KEYWORDS = [
    "sql", "python", "power bi", "tableau", "excel",
    "etl", "dax", "power query", "pandas",
]
SKILL_POINT, SKILL_CAP = 5, 25


def score_job(job: dict) -> int:
    title = job.get("title", "").lower()
    haystack = title + " " + job.get("summary", "").lower() + " " + job.get("location", "").lower()
    pts = 0
    for kw, p in TITLE_POINTS:
        if kw in title:
            pts += p
            break
    for kw, p in LOCATION_POINTS:
        if kw in haystack:
            pts += p
            break
    pts += min(SKILL_CAP, sum(SKILL_POINT for kw in SKILL_KEYWORDS if kw in haystack))
    # freshness dominates: apply fast while postings are new
    age = datetime.now(timezone.utc) - store.parse_date(job.get("published", ""), store.UTC_FMT)
    if age.days <= 1:
        pts += 50
    elif age.days <= 3:
        pts += 40
    elif age.days <= 7:
        pts += 25
    elif age.days <= 14:
        pts += 10
    return pts


def _page(title: str, max_width: str, extra_css: str, body: str) -> str:
    """Shared page shell: palette, head, base CSS. Both renderers go through here."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{_PALETTE}
* {{ box-sizing: border-box; }}
body {{
  margin: 0 auto; padding: 2.5rem 1.5rem; max-width: {max_width};
  background: var(--cream); color: var(--espresso);
  font: 15px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
}}
h1, h2 {{ color: var(--mocha); font-weight: 600; }}
.muted {{ color: var(--latte); font-size: .85rem; }}
.card {{
  background: var(--card); border: 1px solid var(--line);
  border-radius: .75rem; padding: 1rem 1.25rem;
}}
{extra_css}
</style>
</head>
<body>
{body}
</body>
</html>"""


_DASH_CSS = """h1 { margin: 0 0 .25rem; font-size: 1.6rem; }
h2 { margin: 0 0 .75rem; font-size: 1.05rem; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.75rem 0; }
.stat-label { margin: 0; font-size: .8rem; color: var(--latte); }
.stat-value { margin: .2rem 0 0; font-size: 2rem; font-weight: 700; color: var(--mocha); }
.stat-value.accent { color: var(--caramel); }
.panels { display: grid; grid-template-columns: 1fr; gap: 1.25rem; }
@media (min-width: 768px) { .panels { grid-template-columns: 1fr 1fr; } }
table { width: 100%; border-collapse: collapse; font-size: .875rem; }
th, td { padding: .5rem .6rem; text-align: left; border-bottom: 1px solid var(--line); }
th { color: var(--latte); font-weight: 500; }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; color: var(--caramel); font-weight: 600; }
a.apply {
  display: inline-block; padding: .2rem .7rem; border-radius: .5rem;
  background: var(--mocha); color: var(--cream); text-decoration: none;
  font-size: .8rem; font-weight: 600;
}
a.apply:hover { background: var(--caramel); }
tr.done td { opacity: .45; }"""


def _build_html(
    total_jobs: int,
    jobs_week: int,
    feed_breakdown: list[tuple[str, int]],
    ranked_jobs: list[dict],
    total_apps: int,
    apps_week: int,
) -> str:
    # escape at the render boundary — feed data is untrusted
    feed_rows = "".join(
        f"<tr><td>{escape(label)}</td>"
        f"<td class='num'>{count}</td></tr>"
        for label, count in feed_breakdown
    )
    job_rows = []
    for j in ranked_jobs:
        applied = store.get_status(j) != "new"  # anything past 'new' is applied to
        link = j.get("link", "")
        apply_cell = (
            "<span class='muted'>Applied</span>" if applied
            else f"<a class='apply' href='{escape(link)}' data-id='{escape(j.get('id', ''))}' "
                 f"data-title='{escape(j['title'])}' target='_blank'>Apply</a>" if link
            else "<span class='muted'>—</span>"
        )
        job_rows.append(
            f"<tr{' class=done' if applied else ''}>"
            f"<td class='num'>{j['_score']}</td>"
            f"<td>{escape(j['title'])}</td>"
            f"<td>{escape(j.get('source', ''))}</td>"
            f"<td class='muted'>{escape(j.get('published', ''))}</td>"
            f"<td>{apply_cell}</td></tr>"
        )
    job_rows = "".join(job_rows)
    body = f"""<h1>Job Tracker Dashboard</h1>
<p class="muted">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div class="stats">
  <div class="card">
    <p class="stat-label">Total Jobs</p>
    <p class="stat-value">{total_jobs}</p>
  </div>
  <div class="card">
    <p class="stat-label">Jobs This Week</p>
    <p class="stat-value accent">{jobs_week}</p>
  </div>
  <div class="card">
    <p class="stat-label">Applications</p>
    <p class="stat-value">{total_apps}</p>
  </div>
  <div class="card">
    <p class="stat-label">Applied This Week</p>
    <p class="stat-value accent">{apps_week}</p>
  </div>
</div>

<div class="panels">
  <div class="card">
    <h2>Jobs by Feed</h2>
    <table>
      <thead><tr><th>Feed</th><th class="num">Count</th></tr></thead>
      <tbody>{feed_rows}</tbody>
    </table>
  </div>
</div>

<div class="card" style="margin-top:1.25rem">
  <h2>All Jobs — Ranked</h2>
  <p class="muted" style="margin:0 0 .75rem">Points: freshness (≤1d 50 / ≤3d 40 / ≤7d 25 / ≤14d 10) + title match (DA 30 / BA·AE 20) + remote 20 / India 10 + resume skills (5 each, max 25)</p>
  <table>
    <thead><tr><th class="num">Score</th><th>Title</th><th>Source</th><th>Published</th><th>Apply</th></tr></thead>
    <tbody>{job_rows}</tbody>
  </table>
</div>
<script>
// served over http: Apply routes through the prep page; file:// keeps direct links
if (location.protocol.startsWith('http'))
  document.querySelectorAll('a.apply').forEach(a =>
    a.href = '{PREP_ROUTE}' + encodeURIComponent(a.dataset.id));

// remember which Apply links were clicked; ask about them on revisit
const KEY = 'pendingApply';
const load = () => JSON.parse(localStorage.getItem(KEY) || '{{}}');
const save = p => localStorage.setItem(KEY, JSON.stringify(p));

document.querySelectorAll('a.apply').forEach(a =>
  a.addEventListener('click', () => {{
    const p = load();
    p[a.dataset.id] = a.dataset.title;
    save(p);
  }})
);

let asking = false;
async function askPending() {{
  if (asking) return;
  asking = true;
  const p = load();
  for (const [id, title] of Object.entries(p)) {{
    const yes = confirm('Did you apply to:\\n\\n' + title + '?');
    delete p[id];
    save(p);
    if (yes) {{
      await fetch('{APPLIED_ROUTE}' + encodeURIComponent(id), {{method: 'POST'}});
      location.reload();
      return;
    }}
  }}
  asking = false;
}}

window.addEventListener('load', askPending);
document.addEventListener('visibilitychange', () => {{
  if (!document.hidden) askPending();
}});
</script>"""
    return _page("Job Tracker Dashboard", "64rem", _DASH_CSS, body)


_PREP_CSS = """h1 { margin: 0; font-size: 1.4rem; }
h2 { font-size: 1rem; margin: 1.5rem 0 .5rem; }
.card { margin-top: .5rem; }
pre { white-space: pre-wrap; font: inherit; margin: 0; }
button.copy { float: right; border: 1px solid var(--line); background: var(--cream);
              color: var(--mocha); border-radius: .5rem; padding: .15rem .6rem; cursor: pointer; }
a.go { display: inline-block; margin-top: 1.5rem; padding: .5rem 1.1rem; border-radius: .5rem;
       background: var(--mocha); color: var(--cream); text-decoration: none; font-weight: 600; }
a.go:hover { background: var(--caramel); }"""


def render_prep(job: dict, prep: dict) -> str:
    """Tailored-materials page shown when Apply is clicked (served mode only)."""
    bullets = "".join(
        f"<li>{escape(b.strip())}</li>"
        for b in prep.get("tailored_bullets", "").split(" | ") if b.strip()
    )
    missing = escape(prep.get("missing_keywords", "")) or "none — resume covers the JD keywords"
    body = f"""<h1>{escape(job['title'])}</h1>
<p class="muted">{escape(job.get('company', ''))} · {escape(job.get('location', ''))} · via {escape(job.get('source', ''))}</p>

<h2>Tailored bullets</h2>
<div class="card"><button class="copy">copy</button><ul id="bullets" style="margin:0;padding-left:1.2rem">{bullets}</ul></div>

<h2>Missing keywords <span class="muted">(in the JD, not in your resume)</span></h2>
<div class="card">{missing}</div>

<h2>Cover snippet</h2>
<div class="card"><button class="copy">copy</button><pre>{escape(prep.get('cover_snippet', ''))}</pre></div>

<a class="go" href="{escape(job.get('link', ''))}" target="_blank">Go to job posting →</a>
<p class="muted">Saved to application_prep.csv. Paste the bullets + cover into your AI of choice to polish.</p>

<script>
document.querySelectorAll('button.copy').forEach(b =>
  b.addEventListener('click', () => {{
    navigator.clipboard.writeText(b.parentElement.innerText.replace(/^copy\\n?/, ''));
    b.textContent = 'copied'; setTimeout(() => b.textContent = 'copy', 1200);
  }})
);
</script>"""
    return _page(f"Prep — {escape(job['title'])}", "44rem", _PREP_CSS, body)


def render() -> str:
    """Load the store and return the dashboard as an HTML string."""
    all_jobs = store.load_jobs()
    # only show jobs published in the last 21 days
    jobs = store.this_week(all_jobs, "published", store.UTC_FMT, days=21)
    # applications come from the full store, not the window — an old posting you
    # applied to still counts
    apps = [j for j in all_jobs if store.get_status(j) != "new"]

    jobs_week = store.this_week(jobs, "published", store.UTC_FMT)
    apps_week = store.this_week(apps, "status_date")

    feed_breakdown = Counter(j.get("source", "Unknown") for j in jobs).most_common()

    for j in jobs:
        j["_score"] = score_job(j)
    # newest first, then stable-sort by score so ties stay newest-first
    jobs.sort(key=lambda j: j.get("published", ""), reverse=True)
    ranked = sorted(jobs, key=lambda j: -j["_score"])

    return _build_html(
        total_jobs=len(jobs),
        jobs_week=len(jobs_week),
        feed_breakdown=feed_breakdown,
        ranked_jobs=ranked,
        total_apps=len(apps),
        apps_week=len(apps_week),
    )


def main(open_browser: bool = False) -> None:
    DASHBOARD_PATH.write_text(render(), encoding="utf-8")
    print(f"[OK] Dashboard written to {DASHBOARD_PATH}")

    if open_browser:
        webbrowser.open(DASHBOARD_PATH.resolve().as_uri())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate job tracker dashboard")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser")
    args = parser.parse_args()
    main(open_browser=args.open)
