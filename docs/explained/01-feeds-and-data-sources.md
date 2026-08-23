# 01 — Feeds and where jobs come from

Argus reads job listings from RSS feeds. This file explains what RSS is, how a
site with no feed still becomes a feed, and what the resulting links really
point to.

All feeds live in `config.toml` under `[[discovery.feeds]]`. The code that reads
them is `discover.py`.

---

## 1. What RSS is

RSS is a plain XML file that a website publishes and keeps updating. Nothing
more. It looks like this:

```xml
<rss><channel>
  <title>Remote Data Jobs</title>
  <item>
    <title>Data Analyst</title>
    <link>https://example.com/jobs/123</link>
    <pubDate>Sat, 23 Aug 2026 09:00:00 GMT</pubDate>
    <description>SQL, Power BI, 2 years...</description>
  </item>
  <item>...</item>
</channel></rss>
```

One `<channel>` holds many `<item>` elements. Each item is one job.

Argus does four things with it, in `discover.py`:

1. **Fetch** — `fetch_feed()` calls `feedparser.parse(url)`. This is a plain
   HTTP GET. `feedparser` turns the XML into Python objects.
2. **Read the fields** — `process_feed()` takes `title`, `link`, `author`,
   `summary`, and the publication date from each item. It drops anything older
   than the `--days` window.
3. **Filter** — keep the job only if its text matches a `role_keywords` entry
   **and** its title contains no `seniority_block` word.
4. **Store** — write the survivors to `jobs_found.csv`, and skip any ID already
   seen.

There is no scraping and no API key. The site hands over structured data because
it wants to be read this way.

### Feed health

`python discover.py --check` prints one line per feed and writes nothing:

```
WWR | All                      |  88 entries | bozo=False | Grafana Labs: Associate Observability Architect
Himalayas | Remote             | 100 entries | bozo=False | Principal Software Engineer, Financial Data Platform
Naukri | DA India              | 100 entries | bozo=False | Data Analyst - Gurugram,Bengaluru - Lenskart - 0 to 5 years
RemoteOK | Data                |   0 entries | bozo=1    | N/A
```

`bozo=1` means `feedparser` found malformed XML. `bozo=1` with entries above
zero is acceptable — Himalayas has done this. `bozo=1` with **zero** entries
means the feed is broken. Both RemoteOK feeds are in that state
(`mismatched tag`).

---

## 2. How Google News turns any site into a feed

Google News is not a job board. It is a search engine with an RSS output mode.

| URL | Returns |
|---|---|
| `news.google.com/search?q=X` | a web page for humans |
| `news.google.com/rss/search?q=X` | the same results as RSS XML |

So you write a normal search query and receive a machine-readable feed. The
Naukri query is:

```
site:naukri.com "data analyst"
```

- `site:` limits results to one domain.
- `hl=en-IN&gl=IN&ceid=IN:en` sets language and country to India.

**Why this matters:** Naukri publishes no feed, but Google already crawls
Naukri. You borrow Google's crawler.

### Naukri has no RSS. Verified.

`https://www.naukri.com/rss-feed-jobs` is **not** a feed. It is Naukri's normal
job-search page for the keyword "rss feed". Naukri's URL pattern is
`/<keyword>-jobs`, so `rss-feed-jobs` searches for jobs that mention "rss feed".
The page returns `text/html` and its embedded state confirms the reading:

```
"routeKeyword":"rss-feed","keyword":"rss-feed"
```

`/rss-feeds-jobs` and `/rss-jobs` behave the same way.

Naukri also blocks non-browser clients. `curl` with no User-Agent times out. A
browser User-Agent gets `200`. `feedparser` sends its own User-Agent, so it
would be blocked even if a feed existed.

These paths return `404`: `/rss/jobs`, `/rssfeed`, `/jobs.rss`.

Conclusion: there is no public Naukri RSS endpoint. The Google News route is the
workaround, and `news.google.com` blocks nobody.

---

## 3. The LinkedIn feeds use the same trick

LinkedIn publishes no jobs RSS either. The four LinkedIn feeds in `config.toml`
are the same mechanism with a different filter:

```
site:linkedin.com/jobs "data analyst India"
```

**Argus never contacts LinkedIn.** It reads Google's index of LinkedIn.

### What the stored link actually is

The `link` column in `jobs_found.csv` is a Google redirect URL, not a LinkedIn
or Naukri URL:

```
https://news.google.com/rss/articles/CBMiuwFBVV95cUxPX05XTkExX1Fo...
```

Tested behaviour: the URL returns `302` to itself with locale parameters, then
serves a page that resolves the real target **in JavaScript**. So:

- **In a browser** — the user clicks the dashboard link, Google's page runs, and
  they land on the LinkedIn or Naukri job. This works.
- **From a script** — following redirects with `curl` never reaches the target.
  The destination URL is not present in the HTML.

The job `id` is derived from that redirect URL, so IDs are long base64 strings.

---

## 4. Trade-offs of the Google News route

| Limit | Effect |
|---|---|
| Google's index, not live search | New postings appear late. Some never appear. |
| Title is the only structured field | Company, location, and experience must be parsed out of the title string. |
| `id` derives from the redirect blob | If Google re-indexes with a different blob, one job can look like two. |
| Login walls | Viewing or applying on Naukri or LinkedIn can still need an account. |

Note also that `max_per_feed = 25` caps how many entries each feed contributes.
A feed that returns 100 entries still offers at most 25 candidates per run.
