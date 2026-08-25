#!/usr/bin/env python3
"""Preview docs/ the way Cloudflare Pages serves it.

Two things stop you just opening the HTML:

  - every asset and link is an absolute path (/style.css, /Entity), and under
    file:// those resolve against the filesystem root, so you get no stylesheet
    and no working links;
  - Pages maps /Entity to Entity.html for you. `python3 -m http.server` does
    not, so every link on the site 404s.

This does both. Run it, open the URL, click around.

    python3 scripts/serve.py            # http://localhost:8788
    python3 scripts/serve.py 9000       # another port

`npx wrangler pages dev docs` is the same thing via the real Pages runtime, if
you have node to hand and want to check _headers as well.
"""
from __future__ import annotations

import functools
import http.server
import re
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Straight out of docs/_headers, so a .ttl fetched from here parses at the other
# end just as it would in production.
TYPES = {
    # Pages sends a charset on these; stdlib does not. Without it the browser
    # guesses, and a page whose curly quotes come out as mojibake sends you
    # hunting for an encoding bug that is not in the file.
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".ttl": "text/turtle; charset=utf-8",
    ".nt": "application/n-triples; charset=utf-8",
    ".rdf": "application/rdf+xml; charset=utf-8",
    ".jsonld": "application/ld+json; charset=utf-8",
    ".trig": "application/trig; charset=utf-8",
    ".nq": "application/n-quads; charset=utf-8",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        got = super().translate_path(path)
        p = Path(got)
        # /Entity -> Entity.html, which is the one thing a plain static server
        # will not do and every link here depends on.
        if not p.exists() and not p.suffix and p.with_suffix(".html").exists():
            return str(p.with_suffix(".html"))
        return got

    def guess_type(self, path):
        suffix = Path(path).suffix
        return TYPES.get(suffix) or super().guess_type(path)

    def end_headers(self):
        # No caching, so a rebuild shows up on reload rather than on a hard one.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        code = args[1] if len(args) > 1 else ""
        if str(code) != "200":
            super().log_message(fmt, *args)


def main() -> None:
    if not DOCS.exists():
        raise SystemExit("docs/ is not built yet — run: python3 scripts/build.py")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    handler = functools.partial(Handler, directory=str(DOCS))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        # flush: this line is the whole point of running the thing, and a piped
        # stdout would otherwise hold it back until the buffer fills.
        print(f"loze  →  http://localhost:{port}", flush=True)
        print("        /terms  /examples        (ctrl-c to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
