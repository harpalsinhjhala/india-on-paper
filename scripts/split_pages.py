"""Write data/raw/extracted_pages.json (output of extract_pdf_text.js) to one text file per report."""
import json
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def main():
    docs = json.loads((RAW / "extracted_pages.json").read_text(encoding="utf-8"))
    out = RAW / "text"
    out.mkdir(exist_ok=True)
    for name, pages in docs.items():
        with open(out / f"{name}.txt", "w", encoding="utf-8") as f:
            for i, p in enumerate(pages, 1):
                f.write(f"\n===== PAGE {i} =====\n{p}\n")
        print(name, len(pages), "pages")


if __name__ == "__main__":
    main()
