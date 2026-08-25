# previews

Full-page screenshots for reviewing a styling change, taken with Playwright
against a local server. Not part of the site: `scripts/build.py` neither reads
nor writes this directory, and nothing under `docs/` links to it.

Regenerate:

    python3 scripts/build.py
    (cd docs && python3 -m http.server 8791 &)
    npx playwright screenshot --browser chromium --viewport-size 1280,1000 \
      --full-page --color-scheme dark --wait-for-timeout 3000 \
      http://localhost:8791/index.html previews/index-dark.png

Serve them rather than opening `docs/index.html` directly — pages link the
stylesheet as `/style.css`, which over `file://` resolves to the filesystem root
and silently loads nothing. A screenshot taken that way is of an unstyled page,
and light and dark come out byte-identical.
