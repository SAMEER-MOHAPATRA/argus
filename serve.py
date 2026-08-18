"""
serve.py — serves the dashboard locally with an apply-confirmation endpoint.

Usage:
    python serve.py      # opens http://localhost:8765/
"""

import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

import dashboard
import prep
import store

PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(dashboard.PREP_ROUTE):
            job_id = unquote(self.path.rsplit("/", 1)[-1])
            job = next((j for j in store.load_jobs() if j.get("id") == job_id), None)
            if job is None:
                self.send_error(404)
                return
            # fetches the live JD, tailors bullets/cover, upserts application_prep.csv
            body = dashboard.render_prep(job, prep.prep_one(job)).encode("utf-8")
        elif self.path in ("/", "/dashboard.html"):
            # render fresh per visit; never writes dashboard.html (CLI-only artifact)
            body = dashboard.render().encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        job_id = self.path.rsplit("/", 1)[-1]
        if self.path.startswith(dashboard.APPLIED_ROUTE) and store.set_status(job_id, "applied"):
            self.send_response(204)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, *args):  # quiet console
        pass


def _already_running() -> bool:
    # ponytail: Windows SO_REUSEADDR lets a busy port re-bind without OSError,
    # so probe by connecting instead of catching a bind error.
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


if __name__ == "__main__":
    url = f"http://localhost:{PORT}/"
    webbrowser.open(url)  # always open a fresh tab
    if _already_running():
        print(f"Dashboard already running at {url}")
    else:
        print(f"Dashboard at {url}  (Ctrl+C to stop)")
        HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
