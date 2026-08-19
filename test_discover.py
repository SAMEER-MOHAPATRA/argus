"""Checks on feed parsing: sanitize_html.

Run: python test_discover.py
"""

import discover

# sanitize_html strips tags, decodes entities, collapses whitespace
assert discover.sanitize_html("<p>Data &amp;  Analyst</p>") == "Data & Analyst"
assert discover.sanitize_html("<br/>Remote\n\n  (EU)") == "Remote (EU)"
assert discover.sanitize_html("") == ""

print("OK: test_discover passed")
