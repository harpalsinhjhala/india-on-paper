"""Inline dashboard/data.json into dashboard/template.html.

Writes two files:
  dashboard/index.html  page body only (the Claude artifact host adds the document skeleton)
  docs/index.html       full standalone HTML document, served by GitHub Pages
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
DOCS = ROOT / "docs"

SKELETON_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Ten years of India's income-tax return data analysed: percentiles, salaried vs business filers, the top 1%, black-money signals, household and city incomes. A portfolio project by Harpal Sinh Jhala.">
<meta name="author" content="Harpal Sinh Jhala">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def main():
    tpl = (DASH / "template.html").read_text(encoding="utf-8")
    data = (DASH / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
    assert "/*__DATA__*/null" in tpl
    page = tpl.replace("/*__DATA__*/null", data)

    out = DASH / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

    # standalone document: everything up to the first </style> is head content
    cut = page.index("</style>") + len("</style>")
    standalone = SKELETON_HEAD + page[:cut] + "\n</head>\n<body>\n" + page[cut:] + "\n</body>\n</html>\n"
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(standalone, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {DOCS / 'index.html'} ({(DOCS / 'index.html').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
