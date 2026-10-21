# ITR analytics — India on Paper

*A portfolio project by Harpal Sinh Jhala.*

**Live dashboard:** https://harpalsinhjhala13.github.io/india-on-paper/

A dashboard built on ten years of India's public income-tax return statistics (AY 2014-15 to AY 2023-24,
the latest CBDT has published), answering:

1. Where does an income rank? (percentile calculator: salaried, business, all filers, all Indians)
2. Job-goers vs business owners
3. The top 1%: who they are and what share they hold
4. Is there black money in the data? (bunching at the ₹5 lakh rebate cliff, TDS non-filers, crorepati mix)
5. Rich on feel, poor on paper (filers vs population, declared income vs GDP)
6. Average vs median income
7. Top cities / states driving collections

Open the live link above, or open `docs/index.html` in a browser. It is a single self-contained file.

## Folder layout

```
data/raw/pdf/            official CBDT PDFs (10 ITR statistics reports + Time Series FY2000-01..2024-25)
data/raw/text/           page text extracted from each PDF
data/processed/
  itr_range_tables.csv       every slab table: AY × status × measure × income slab (14k rows)
  headline_metrics_by_year.csv   percentiles, top shares, Gini, crorepatis, medians… per AY
  timeseries_macro.csv       collections, GDP, filers, taxpayers, population
  timeseries_states.csv      state-wise direct tax collections FY2018-19..2024-25
dashboard/
  template.html   dashboard source
  data.json       computed insights
  index.html      built dashboard (page body, used for the Claude artifact)
docs/index.html   standalone copy served by GitHub Pages
scripts/          pipeline (below)
```

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/extract_pdf_text.js` | Fetches the PDFs and extracts page text with pdf.js. **Runs in a browser** on incometaxindia.gov.in, because the site's CDN blocks scripted downloads (HTTP 403). |
| 2 | `scripts/split_pages.py` | Splits that JSON into `data/raw/text/*.txt` |
| 3 | `scripts/parse_itr_tables.py` | Parses every "Range of …" table and validates each against its printed Total row |
| 4 | `scripts/build_timeseries.py` | Macro + state series transcribed from the Time Series PDF |
| 5 | `scripts/compute_insights.py` | Percentiles, top shares, Gini, bunching, population/GDP ratios → `dashboard/data.json` |
| 6 | `scripts/build_dashboard.py` | Inlines the data into `dashboard/index.html` and `docs/index.html` (GitHub Pages) |

```bash
python scripts/parse_itr_tables.py && python scripts/build_timeseries.py && python scripts/compute_insights.py && python scripts/build_dashboard.py
```

When CBDT publishes AY 2024-25, add its PDF link to `extract_pdf_text.js`, rerun steps 1–6.

## Method notes

- **Percentiles** use a truncated-Pareto fit inside each CBDT slab that reproduces the slab's published
  count and average exactly; the open top slab is a plain Pareto.
- All Individual tables (GTI, salary, business, capital gains, returned income, tax payable) reconcile to
  their Total rows for all ten years. A handful of HUF/Firm/AOP tables did not parse cleanly and are not used.
- **Bunching ratio** = returns in ₹4.5–5L ÷ returns in ₹5–5.5L (equal-width slabs). The Sec 87A rebate
  made taxable income up to ₹5L tax-free from AY 2020-21 (₹3.5L in AY 2018-19 and 2019-20).
- External context used in the dashboard (labelled there): World Bank population, Hurun India Wealth
  Report 2025, luxury-car sales 2024.
