"""Turn the parsed CBDT tables into dashboard-ready insights (dashboard/data.json).

Distributional method
---------------------
CBDT publishes, for each income slab [a, b], the number of returns and their mean.
Inside each slab we fit a truncated Pareto density whose mean matches the published
mean exactly (alpha solved by bisection); the open top slab gets an untruncated Pareto
(alpha = m / (m - a)); the first slab (0, b] gets a power density x^k matching its mean.
That gives a continuous CDF from which percentiles, top-income shares and the
"what percentile am I?" curves are read.  Every slab's count and income total is
preserved exactly, so the only modelling choice is the shape within a slab.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "data.json"

tables = pd.read_csv(PROC / "itr_range_tables.csv", dtype={"assessment_year": str})
macro = pd.read_csv(PROC / "timeseries_macro.csv")
states = pd.read_csv(PROC / "timeseries_states.csv")
YEARS = sorted(tables.assessment_year.unique())


# ---------------------------------------------------------------- slab model
def _tp_mean(alpha, a, b):
    """Mean of a Pareto(alpha) truncated to [a, b]."""
    r = a / b
    if abs(alpha) < 1e-9:  # density ~ 1/x
        return (b - a) / math.log(b / a)
    if abs(alpha - 1) < 1e-9:
        return a * math.log(b / a) / (1 - r)
    return alpha * a ** alpha / (1 - r ** alpha) * (a ** (1 - alpha) - b ** (1 - alpha)) / (alpha - 1)


def fit_alpha(m, a, b):
    lo, hi = -60.0, 60.0  # mean is decreasing in alpha
    m = min(max(m, a * 1.0001), b * 0.9999)
    for _ in range(200):
        mid = (lo + hi) / 2
        if _tp_mean(mid, a, b) > m:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class Slab:
    def __init__(self, a, b, n, total):
        self.a, self.b, self.n, self.total = a, b, n, total
        self.m = total / n if n else 0.0
        if n == 0:
            self.kind = "empty"
        elif b is None:
            self.kind = "pareto"
            self.alpha = self.m / (self.m - a) if self.m > a else 50.0
        elif a == 0:
            self.kind = "power"
            r = min(max(self.m / b, 0.01), 0.99)
            self.k = (2 * r - 1) / (1 - r)
        else:
            self.kind = "tpareto"
            self.alpha = fit_alpha(self.m, a, b)

    def cdf(self, x):
        """Share of this slab's returns with value <= x."""
        if self.kind == "empty":
            return 0.0
        a, b = self.a, self.b
        if x <= a:
            return 0.0
        if b is not None and x >= b:
            return 1.0
        if self.kind == "power":
            return (x / b) ** (self.k + 1)
        if self.kind == "pareto":
            return 1 - (a / x) ** self.alpha
        al = self.alpha
        if abs(al) < 1e-9:
            return math.log(x / a) / math.log(b / a)
        return (1 - (a / x) ** al) / (1 - (a / b) ** al)

    def quantile(self, u):
        """Inverse CDF inside the slab, u in [0, 1]."""
        a, b = self.a, self.b
        if self.kind == "power":
            return b * u ** (1 / (self.k + 1))
        if self.kind == "pareto":
            return a / (1 - u) ** (1 / self.alpha)
        al = self.alpha
        if abs(al) < 1e-9:
            return a * (b / a) ** u
        return a / (1 - u * (1 - (a / b) ** al)) ** (1 / al)

    def income_above(self, x):
        """Total income (same units as total) held by returns in this slab with value > x."""
        if self.kind == "empty" or (self.b is not None and x >= self.b):
            return 0.0
        if x <= self.a:
            return self.total
        # numeric: integrate the quantile function over the upper part of the slab
        u0 = self.cdf(x)
        us = np.linspace(u0, 1, 4001)[:-1] + (1 - u0) / 8000
        vals = np.array([self.quantile(u) for u in us])
        est = vals.mean() * (1 - u0) * self.n
        # rescale so the full-slab integral matches the published total exactly
        full = np.array([self.quantile(u) for u in (np.arange(4000) + 0.5) / 4000]).mean() * self.n
        return est * (self.total / full) if full else 0.0


class Dist:
    """Distribution of one measure for one year, built from CBDT slabs (INR)."""

    def __init__(self, df, include_zero=True):
        df = df.sort_values("slab_order")
        self.zero = int(df.loc[df.slab == "=0", "returns"].sum()) + int(df.loc[df.slab == "<0", "returns"].sum())
        self.slabs = [Slab(r.lower_inr, None if pd.isna(r.upper_inr) else r.upper_inr, r.returns, r.sum_crore * 1e7)
                      for r in df[df.slab_order >= 2].itertuples()]
        self.pos_n = sum(s.n for s in self.slabs)
        self.N = self.pos_n + (self.zero if include_zero else 0)
        self.base = self.zero if include_zero else 0
        self.total = sum(s.total for s in self.slabs)

    def share_below(self, x):
        c = self.base
        for s in self.slabs:
            c += s.n * s.cdf(x)
        return c / self.N

    def quantile(self, p):
        target = p * self.N
        if target <= self.base:
            return 0.0
        c = self.base
        for s in self.slabs:
            if s.n and c + s.n >= target:
                return s.quantile((target - c) / s.n)
            c += s.n
        return self.slabs[-1].quantile(0.999999)

    def top_share(self, p_top):
        """Share of total income going to the top p_top fraction of returns."""
        thr = self.quantile(1 - p_top)
        return sum(s.income_above(thr) for s in self.slabs) / self.total

    def count_above(self, x):
        return self.N * (1 - self.share_below(x))

    def mean(self):
        return self.total / self.N

    def gini(self):
        # Lorenz curve from a dense quantile grid
        ps = np.concatenate([np.linspace(0, 0.99, 991), 1 - np.logspace(-2, -6, 400)])
        qs = np.array([self.quantile(p) for p in ps])
        w = np.diff(np.append(ps, 1.0))
        inc = qs * w
        L = np.cumsum(inc) / inc.sum()
        return float(1 - np.sum(w * (L + np.concatenate([[0], L[:-1]]))))


def dist(year, measure, include_zero=True, status="Individual"):
    df = tables[(tables.assessment_year == year) & (tables.status == status) & (tables.measure == measure)]
    return Dist(df, include_zero) if len(df) else None


# --------------------------------------------------------------- insights
PCTS = [10, 25, 50, 75, 90, 95, 99, 99.9, 99.99]
CURVE_P = [round(x, 4) for x in list(np.arange(1, 99, 1)) + [99, 99.5, 99.9, 99.95, 99.99, 99.999]]


def lakh(x):
    return round(x / 1e5, 3)


def per_year():
    out = []
    for y in YEARS:
        g = dist(y, "gross_total_income")
        sal = dist(y, "salary", include_zero=False)
        bus = dist(y, "business", include_zero=False)
        ret = dist(y, "returned_income")
        tax = dist(y, "tax_payable")
        if g is None:
            continue
        rec = dict(ay=y, filers=g.N)
        rec["gti_total_cr"] = round(g.total / 1e7)
        rec["gti_mean_l"] = lakh(g.mean())
        rec["gti_pcts_l"] = {str(p): lakh(g.quantile(p / 100)) for p in PCTS}
        rec["gti_median_l"] = rec["gti_pcts_l"]["50"]
        rec["top_share"] = {k: round(100 * g.top_share(v), 2) for k, v in
                            {"top10": .10, "top1": .01, "top0_1": .001, "top0_01": .0001}.items()}
        rec["bottom50_share"] = round(100 - 100 * g.top_share(0.5), 2)
        rec["gini"] = round(g.gini(), 3)
        df = tables[(tables.assessment_year == y) & (tables.status == "Individual")]

        def cnt(measure, lo):
            d = df[(df.measure == measure) & (df.lower_inr >= lo) & (df.slab_order >= 2)]
            return int(d.returns.sum()), round(float(d.sum_crore.sum()))

        rec["crorepati_gti"], rec["crorepati_gti_income_cr"] = cnt("gross_total_income", 10_000_000)
        rec["above_50l_gti"], _ = cnt("gross_total_income", 5_000_000)
        rec["above_100cr_gti"], _ = cnt("gross_total_income", 1_000_000_000)
        rec["crorepati_salary"], rec["crorepati_salary_income_cr"] = cnt("salary", 10_000_000)
        rec["crorepati_business"], rec["crorepati_business_income_cr"] = cnt("business", 10_000_000)
        for name, d in (("salary", sal), ("business", bus)):
            rec[name] = dict(n=d.N, total_cr=round(d.total / 1e7), mean_l=lakh(d.mean()),
                             pcts_l={str(p): lakh(d.quantile(p / 100)) for p in PCTS},
                             top1_share=round(100 * d.top_share(0.01), 2),
                             curve=[lakh(d.quantile(p / 100)) for p in CURVE_P])
        rec["gti_curve"] = [lakh(g.quantile(p / 100)) for p in CURVE_P]
        # Population view: AY t+1 returns report income earned in FY t, i.e. calendar year ~t.
        mrow = macro[macro.ay == y]
        if len(mrow):
            mrow = mrow.iloc[0]
            pop = mrow.population_m * 1e6
            # income reported in AY y was earned in FY (y - 1)
            fy_label = f"{int(y[:4]) - 1}-{y[2:4]}"
            gdp_row = macro[macro.fy == fy_label]
            rec["population"] = int(macro[macro.fy == fy_label].population_m.iloc[0] * 1e6) if len(gdp_row) else int(pop)
            rec["filers_pct_population"] = round(100 * g.N / rec["population"], 2)
            if len(gdp_row):
                rec["gdp_cr"] = float(gdp_row.gdp_cr.iloc[0])
                rec["gti_pct_gdp"] = round(100 * (g.total / 1e7) / rec["gdp_cr"], 1)
                rec["gdp_per_capita_l"] = lakh(rec["gdp_cr"] * 1e7 / rec["population"])
            tp = macro[macro.taxpayer_ay == y]
            rec["taxpayers_individual"] = int(tp.taxpayers_individual.iloc[0])
            rec["tds_non_filers"] = rec["taxpayers_individual"] - g.N
            # entry ticket to the top 1% of ALL Indians (assumes non-filers declare less than filers)
            rec["pop_top1_threshold_l"] = lakh(g.quantile(1 - 0.01 * rec["population"] / g.N))
        if ret is not None:
            rec["returned_median_l"] = lakh(ret.quantile(0.5))
            rec["returned_mean_l"] = lakh(ret.mean())
        if tax is not None:
            rec["zero_tax_returns"] = tax.zero
            rec["zero_tax_pct"] = round(100 * tax.zero / tax.N, 1)
            rec["tax_total_cr"] = round(tax.total / 1e7)
            top1_tax = tax.top_share(0.01)
            rec["tax_top1_share"] = round(100 * top1_tax, 1)
        out.append(rec)
    return out


def slab_table(y, measure):
    df = tables[(tables.assessment_year == y) & (tables.status == "Individual") & (tables.measure == measure)]
    df = df[df.slab_order >= 1].sort_values("slab_order")
    return [dict(slab=r.slab, lo=r.lower_inr, hi=None if pd.isna(r.upper_inr) else r.upper_inr,
                 n=int(r.returns), sum_cr=r.sum_crore, avg_l=r.avg_lakh) for r in df.itertuples()]


def bunching():
    """Density just below vs just above the INR 5 lakh rebate cliff (Sec 87A).

    Slabs 4.5-5L and 5-5.5L are both 50k wide, so the count ratio is a density ratio.
    A smooth distribution gives ~1x; self-reported income piling up below a tax cliff gives >>1x.
    """
    out = []
    for y in YEARS:
        df = tables[(tables.assessment_year == y) & (tables.status == "Individual")]
        rec = dict(ay=y)
        for m in ("gross_total_income", "salary", "business", "returned_income"):
            d = df[df.measure == m]
            below = d.loc[d.lower_inr == 450_000, "returns"].sum()
            above = d.loc[d.lower_inr == 500_000, "returns"].sum()
            below2 = d.loc[d.lower_inr == 400_000, "returns"].sum()
            rec[m] = dict(r400=int(below2), r450=int(below), r500=int(above),
                          ratio=round(below / above, 2) if above else None)
        out.append(rec)
    return out


def income_mix(y):
    """Where individual income comes from, by GTI-equivalent head (INR crore)."""
    df = tables[(tables.assessment_year == y) & (tables.status == "Individual")]
    tot = {m: float(df[(df.measure == m) & (df.slab_order != 0)].sum_crore.sum())
           for m in ("salary", "business", "house_property", "ltcg", "stcg", "other_sources")}
    neg = {m: float(df[(df.measure == m) & (df.slab_order == 0)].sum_crore.sum()) for m in tot}
    return {m: round(tot[m] + min(neg[m], 0)) for m in tot}


def top_slab_mix(y):
    """In each high-income slab: how many salary earners vs business earners."""
    df = tables[(tables.assessment_year == y) & (tables.status == "Individual")]
    out = []
    for lo in [2_500_000, 5_000_000, 10_000_000, 50_000_000, 100_000_000, 250_000_000, 500_000_000]:
        row = dict(lo=lo)
        for m in ("gross_total_income", "salary", "business"):
            row[m] = int(df[(df.measure == m) & (df.lower_inr == lo)].returns.sum())
        out.append(row)
    return out


BANDS = [(0, 250_000, "Up to ₹2.5L"), (250_000, 500_000, "₹2.5–5L"), (500_000, 1_000_000, "₹5–10L"),
         (1_000_000, 2_500_000, "₹10–25L"), (2_500_000, 5_000_000, "₹25–50L"), (5_000_000, 10_000_000, "₹50L–1Cr"),
         (10_000_000, None, "₹1Cr+")]


def earner_bands():
    """Salary earners vs business earners: how many fall in each income band, and the income they declare."""
    out = {}
    for y in YEARS:
        df = tables[(tables.assessment_year == y) & (tables.status == "Individual") & (tables.slab_order >= 2)]
        rec = {}
        for m in ("salary", "business"):
            d = df[df.measure == m]
            rows = []
            for lo, hi, lab in BANDS:
                sel = d[(d.lower_inr >= lo) & ((d.lower_inr < hi) if hi else True)]
                rows.append(dict(band=lab, n=int(sel.returns.sum()), income_cr=round(float(sel.sum_crore.sum()))))
            rec[m] = rows
        out[y] = rec
    return out


def households_vs_returns(ext):
    """PRICE 2020-21 household classes vs individuals declaring the same income on AY 2021-22 returns (FY 2020-21 income)."""
    g = dist("2021-22", "gross_total_income")
    hh = ext["india"]["2020-21"]["classes_k"]
    rows = []
    for x, lab, keys in [(3_000_000, "₹30L+", ["Near Rich", "Clear Rich", "Sheer Rich", "Super Rich"]),
                         (5_000_000, "₹50L+", ["Clear Rich", "Sheer Rich", "Super Rich"]),
                         (10_000_000, "₹1Cr+", ["Sheer Rich", "Super Rich"]),
                         (20_000_000, "₹2Cr+", ["Super Rich"])]:
        rows.append(dict(label=lab, households=int(sum(hh[k] for k in keys) * 1000), individuals=int(round(g.count_above(x)))))
    return rows


def main():
    ext = json.loads((PROC / "external_households_cities.json").read_text(encoding="utf-8"))
    yrs = per_year()
    latest = yrs[-1]["ay"]
    first = yrs[0]["ay"]
    m = macro.copy()
    data = dict(
        meta=dict(years=[r["ay"] for r in yrs], latest=latest, first=first, curve_p=CURVE_P, pcts=PCTS,
                  source="CBDT Income Tax Return Statistics AY 2014-15 to AY 2023-24; CBDT Time Series Data FY 2000-01 to 2024-25",
                  built=pd.Timestamp.today().strftime("%Y-%m-%d")),
        years=yrs,
        slabs={y: {m_: slab_table(y, m_) for m_ in ("gross_total_income", "salary", "business", "returned_income")}
               for y in [r["ay"] for r in yrs]},
        bunching=bunching(),
        income_mix={r["ay"]: income_mix(r["ay"]) for r in yrs},
        top_slab_mix={r["ay"]: top_slab_mix(r["ay"]) for r in yrs},
        macro=m.to_dict(orient="records"),
        earner_bands=earner_bands(),
        households_vs_returns=households_vs_returns(ext),
        external=ext,
        states=states.to_dict(orient="records"),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), default=float), encoding="utf-8")

    # flat CSV of the headline metrics for analysts
    flat = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (dict, list))} |
                         {f"gti_p{k}_l": v for k, v in r["gti_pcts_l"].items()} |
                         {f"share_{k}": v for k, v in r["top_share"].items()} |
                         {"salary_median_l": r["salary"]["pcts_l"]["50"], "business_median_l": r["business"]["pcts_l"]["50"],
                          "salary_mean_l": r["salary"]["mean_l"], "business_mean_l": r["business"]["mean_l"],
                          "salary_earners": r["salary"]["n"], "business_earners": r["business"]["n"]}
                         for r in yrs])
    flat.to_csv(PROC / "headline_metrics_by_year.csv", index=False)
    print(flat.T.to_string())
    print(json.dumps(data["bunching"][-1], indent=1))
    print(OUT, round(OUT.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
