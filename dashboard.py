"""
dashboard.py — renders the job dashboard and serves it locally.

Serve-only: every visit renders fresh from the store, so there is no
dashboard.html artifact to go stale.

Usage:
    python dashboard.py      # opens http://localhost:8765/
"""

import socket
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote, unquote

import prep
import store

PORT = 8765

# routes are shared by the emitted JS and the Handler below — rename in one place
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
button.mark {
  padding: .2rem .55rem; border-radius: .5rem; cursor: pointer;
  border: 1px solid var(--line); background: var(--cream); color: var(--mocha);
  font: 600 .8rem/1.5 inherit;
}
button.mark:hover:enabled { background: var(--caramel); color: var(--cream); }
button.mark:disabled { opacity: .5; cursor: default; }
tr.done td { opacity: .45; }"""


def _build_html(
    total_jobs: int,
    jobs_week: int,
    feed_breakdown: list[tuple[str, int]],
    ranked_jobs: list[dict],
    total_apps: int,
    apps_week: int,
    recent_apps: list[dict],
) -> str:
    # escape at the render boundary — feed data is untrusted
    feed_rows = "".join(
        f"<tr><td>{escape(label)}</td>"
        f"<td class='num'>{count}</td></tr>"
        for label, count in feed_breakdown
    )
    app_rows = "".join(
        f"<tr><td class='muted'>{escape(a.get('status_date', ''))}</td>"
        f"<td>{escape(a.get('title', ''))}</td>"
        f"<td>{escape(a.get('company', ''))}</td>"
        f"<td>{escape(store.get_status(a).title())}</td></tr>"
        for a in recent_apps
    ) or "<tr><td class='muted' colspan='4'>Nothing yet — mark a job applied below.</td></tr>"
    # the one tip worth keeping from review.py
    pace_tip = (
        '<p class="muted" style="margin:.75rem 0 0">Aim for 3-5 quality applications per week.</p>'
        if apps_week < 3 else ""
    )
    job_rows = []
    for j in ranked_jobs:
        applied = store.get_status(j) != "new"  # anything past 'new' is applied to
        job_id = j.get("id", "")
        if applied:
            apply_cell = f"<span class='muted'>{escape(store.get_status(j).title())}</span>"
        elif j.get("link"):
            # served over http only, so the prep route is rendered here, not patched by JS
            apply_cell = (
                f"<a class='apply' href='{PREP_ROUTE}{quote(job_id)}' target='_blank'>Apply</a> "
                f"<button class='mark' data-id='{escape(job_id)}'>&#10003; Applied</button>"
            )
        else:
            apply_cell = "<span class='muted'>—</span>"
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
  <div class="card">
    <h2>Recent Applications</h2>
    <table>
      <thead><tr><th>Date</th><th>Title</th><th>Company</th><th>Status</th></tr></thead>
      <tbody>{app_rows}</tbody>
    </table>
    {pace_tip}
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
// one click, one write — the server is the only state, nothing cached client-side
document.querySelectorAll('button.mark').forEach(b =>
  b.addEventListener('click', async () => {{
    b.disabled = true;
    const r = await fetch('{APPLIED_ROUTE}' + encodeURIComponent(b.dataset.id),
                          {{method: 'POST'}});
    if (r.ok) location.reload();
    else {{ b.disabled = false; b.textContent = 'failed'; }}
  }})
);
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
    recent_apps = sorted(apps, key=lambda a: a.get("status_date", ""), reverse=True)[:5]

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
        recent_apps=recent_apps,
    )


# ─── Server ──────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(PREP_ROUTE):
            job_id = unquote(self.path.rsplit("/", 1)[-1])
            job = next((j for j in store.load_jobs() if j.get("id") == job_id), None)
            if job is None:
                self.send_error(404)
                return
            # fetches the live JD, tailors bullets/cover, upserts application_prep.csv
            body = render_prep(job, prep.prep_one(job)).encode("utf-8")
        elif self.path in ("/", "/dashboard.html"):
            body = render().encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        job_id = unquote(self.path.rsplit("/", 1)[-1])
        if self.path.startswith(APPLIED_ROUTE) and store.set_status(job_id, "applied"):
            self.send_response(204)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # quiet console
        pass


def _already_running() -> bool:
    # ponytail: Windows SO_REUSEADDR lets a busy port re-bind without OSError,
    # so probe by connecting instead of catching a bind error.
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def serve() -> None:
    """Serve the dashboard on PORT, rendering fresh on every request."""
    url = f"http://localhost:{PORT}/"
    webbrowser.open(url)  # always open a fresh tab
    if _already_running():
        print(f"Dashboard already running at {url}")
        return
    print(f"Dashboard at {url}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    serve()
