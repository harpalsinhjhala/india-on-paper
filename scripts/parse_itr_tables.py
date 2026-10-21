"""Parse CBDT 'Income Tax Return Statistics' range tables into a tidy CSV.

Input : data/raw/text/AY<yyyy-yy>.txt  (page text extracted from the official PDFs)
Output: data/processed/itr_range_tables.csv

One row per (assessment_year, taxpayer status, measure, income slab) with
number of returns, sum of the measure (INR crore) and average (INR lakh).
Every table is validated against its own 'Total' row.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "data" / "raw" / "text"
OUT = ROOT / "data" / "processed" / "itr_range_tables.csv"

# Canonical CBDT slabs (INR). lower bound -> upper bound (None = open ended)
BOUNDS = [0, 150_000, 200_000, 250_000, 350_000, 400_000, 450_000, 500_000, 550_000,
          950_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000, 5_000_000, 10_000_000,
          50_000_000, 100_000_000, 250_000_000, 500_000_000, 1_000_000_000, 5_000_000_000]
SLABS = [("<0", None, 0), ("=0", 0, 0)] + [
    (f">{lo}", lo, BOUNDS[i + 1] if i + 1 < len(BOUNDS) else None) for i, lo in enumerate(BOUNDS)
]
# normalised label text -> slab index
LABELS = {"<0": 0, "=0": 1}
for i, lo in enumerate(BOUNDS):
    hi = BOUNDS[i + 1] if i + 1 < len(BOUNDS) else None
    LABELS[f">{lo}and<={hi}" if hi else f">{lo}"] = i + 2

STATUS = {"1": "All Taxpayers", "2": "Individual", "3": "HUF", "4": "Firm", "5": "AOP/BOI", "6": "Company"}
MEASURES = [
    ("Gross Total Income", "gross_total_income"), ("Salary Income", "salary"),
    ("House Property Income", "house_property"), ("Business Income", "business"),
    ("Long Term Capital Gains", "ltcg"), ("Short Term Capital Gains", "stcg"),
    ("Short-Term Capital Gains", "stcg"), ("Other Sources Income", "other_sources"),
    ("Interest Income", "interest"), ("Loss Set off", "loss_setoff"),
    ("Returned Income", "returned_income"), ("Tax Payable", "tax_payable"),
]
HEADER = re.compile(r"^([1-6])\.(\d{1,2})\b(.*)\(AY\s*20\d\d")


def norm(s):
    return re.sub(r"[\s|,]", "", s).replace("&lt;", "<").replace("&gt;", ">")


def num(tok):
    tok = tok.strip()
    if tok in ("-", "--", ""):
        return 0.0
    return float(tok.replace(",", ""))


def split_label(line, next_line=""):
    """Return (slab_index, numeric tokens, consumed_next) if the line starts with a slab label.

    Handles labels split over two lines, e.g. '>100,00,00,000 and | 15 | ...' + '<=500,00,00,000'.
    """
    toks = [t for t in line.split("|")]
    acc = ""
    for i, t in enumerate(toks):
        acc += t
        n = norm(acc)
        if n in LABELS:
            return LABELS[n], " ".join(toks[i + 1:]).split(), False
        if n.endswith("and") and norm(n + next_line) in LABELS:
            return LABELS[norm(n + next_line)], " ".join(toks[i + 1:]).split(), True
        if not re.fullmatch(r"[<>=]?[\d<>=and.]*", n):
            return None
    return None


NUMERIC_LINE = re.compile(r"^[\d,.\-\s|]+$")


def parse_table(lines):
    items = []  # ("label", idx, nums|None) or ("nums", nums)
    total = None
    skip = False
    for k, ln in enumerate(lines):
        s = re.sub(r"-\s+(?=\d)", "-", ln.strip())  # '- 48,255' is a negative number
        if skip or not s:
            skip = False
            continue
        if re.match(r"^\|?\s*total", s, re.I) and any(it[0] == "label" for it in items):
            nums = re.sub(r"(?i)total", "", s).replace("|", " ").split()
            total = [num(x) for x in nums if re.fullmatch(r"[\d,.\-]+", x)]
            if not total and items and items[-1][0] == "nums":  # totals printed on the line above
                total = items.pop()[1]
            if not total:  # ... or on the line below
                for nxt in lines[k + 1:k + 3]:
                    if NUMERIC_LINE.match(nxt.strip()) and nxt.strip():
                        total = [num(x) for x in nxt.replace("|", " ").split()]
                        break
            break
        nxt = lines[k + 1].strip() if k + 1 < len(lines) else ""
        lab = split_label(s, nxt)
        if lab:
            idx, rest, skip = lab
            nums = [num(x) for x in rest if re.fullmatch(r"[\d,.\-]+", x)]
            items.append(["label", idx, nums if nums else None])
        elif NUMERIC_LINE.match(s):
            items.append(["nums", [num(x) for x in s.replace("|", " ").split()]])
    rows = {}

    def plausible(idx, nums):
        if len(nums) < 3:
            return len(nums) >= 1 and SLABS[idx][0] in ("=0", "<0")
        cnt, tot, avg = nums[:3]
        if cnt == 0:
            return True
        lo, hi = SLABS[idx][1], SLABS[idx][2]
        avg_inr = avg * 1e5
        if lo is not None and lo > 0 and avg_inr < lo * 0.97:
            return False
        if hi is not None and avg_inr > hi * 1.03:
            return False
        return abs(tot * 1e7 / cnt - avg_inr) <= max(0.02 * avg_inr, 2_000)

    used = set()
    for k, it in enumerate(items):
        if it[0] != "label":
            continue
        idx, nums = it[1], it[2]
        if nums is None:
            for j in (k - 1, k + 1):
                if 0 <= j < len(items) and items[j][0] == "nums" and j not in used and plausible(idx, items[j][1]):
                    nums = items[j][1]
                    used.add(j)
                    break
        if nums is None:
            raise ValueError(f"no numbers for slab {SLABS[idx][0]}")
        nums = (nums + [0, 0, 0])[:3]
        rows[idx] = nums
    return rows, total


def parse_year(path):
    ay = path.stem.replace("AY", "")
    text = path.read_text(encoding="utf-8")
    pages = re.split(r"\n===== PAGE \d+ =====\n", text)
    out = []
    for page in pages:
        lines = page.split("\n")
        for i, ln in enumerate(lines):
            s = ln.replace("|", " ")
            s = re.sub(r"\s+", " ", s).strip()
            m = HEADER.match(s)
            if not m or "...." in s:
                continue
            title = m.group(3)
            measure = next((code for name, code in MEASURES if name.lower() in title.lower()), None)
            if measure is None:
                continue
            status = STATUS[m.group(1)]
            try:
                rows, total = parse_table(lines[i + 1:])
            except ValueError as e:
                print(f"  SKIP {ay} {status} {measure}: {e}", file=sys.stderr)
                break
            for idx, (cnt, tot, avg) in sorted(rows.items()):
                label, lo, hi = SLABS[idx]
                out.append(dict(assessment_year=ay, status=status, measure=measure, table=f"{m.group(1)}.{m.group(2)}",
                                slab_order=idx, slab=label, lower_inr=lo, upper_inr=hi,
                                returns=int(cnt), sum_crore=tot, avg_lakh=avg))
            # validate against total row
            cnt_sum = sum(r[0] for r in rows.values())
            amt_sum = sum(r[1] for r in rows.values())
            if total and len(total) >= 2:
                ok_c = abs(cnt_sum - total[0]) <= max(5, 1e-4 * total[0])
                ok_a = abs(amt_sum - total[1]) <= max(5, 2e-3 * abs(total[1]))
                if not (ok_c and ok_a):
                    print(f"  WARN {ay} {status} {measure}: rows={cnt_sum:,.0f}/{amt_sum:,.0f} total={total}", file=sys.stderr)
            else:
                print(f"  WARN {ay} {status} {measure}: no total row", file=sys.stderr)
            break
    return out


def main():
    rows = []
    for p in sorted(TEXT_DIR.glob("AY*.txt")):
        r = parse_year(p)
        print(f"{p.stem}: {len(r)} slab rows, {len({(x['status'], x['measure']) for x in r})} tables")
        rows += r
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(df)} rows)")


if __name__ == "__main__":
    main()
