"""Inline dashboard/data.json into dashboard/template.html -> dashboard/index.html (single self-contained file)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"


def main():
    tpl = (DASH / "template.html").read_text(encoding="utf-8")
    data = (DASH / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
    assert "/*__DATA__*/null" in tpl
    out = DASH / "index.html"
    out.write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
