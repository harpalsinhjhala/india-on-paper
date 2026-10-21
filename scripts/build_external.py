"""Household and city context from non-CBDT sources -> data/processed/external_households_cities.json

CBDT publishes no household or city statistics, so this layer uses:
  * PRICE ICE 360 survey 2021 ("The Rise of India's Middle Class", executive summary),
    Tables 2, 3, 6, 7: households ('000) by annual household income class, 2020-21 prices.
  * Mercedes-Benz Hurun India Wealth Report 2025: millionaire households (net worth >= Rs 8.5 cr) by city.
  * Official district per-capita income from state statistics departments (latest available year).
  * PIB release 1 Aug 2024: ITRs filed for AY 2024-25 by form, up to 31 July 2024.
Medians are interpolated inside the PRICE income classes (log-linear inside each class).
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "external_households_cities.json"

# PRICE income classes, annual household income in Rs '000 at 2020-21 prices
CLASSES = ["Destitute", "Aspirers", "Seekers", "Strivers", "Near Rich", "Clear Rich", "Sheer Rich", "Super Rich"]
BOUNDS = [0, 125, 500, 1500, 3000, 5000, 10000, 20000, None]
GROUP = {"Destitute": "Destitute", "Aspirers": "Aspirers", "Seekers": "Middle class", "Strivers": "Middle class",
         "Near Rich": "Rich", "Clear Rich": "Rich", "Sheer Rich": "Rich", "Super Rich": "Rich"}

# Table 2 / 3: India, households ('000)
INDIA = {
    "2015-16": [46474, 155984, 61140, 10117, 2286, 2024, 1495, 1057],
    "2020-21": [45171, 160792, 77128, 13799, 3263, 3171, 2431, 1807],
    "2030-31 (projected)": [19905, 136171, 135629, 29423, 7494, 9299, 9266, 9096],
    "2046-47 (projected)": [7222, 49796, 208087, 54743, 16163, 24131, 27463, 32720],
}
# Table 4: rural / urban split 2020-21
RURAL_URBAN = {"Rural": [38589, 110925, 37473, 5476, 1255, 1035, 818, 381],
               "Urban": [6582, 49867, 39655, 8323, 2008, 2136, 1614, 1426]}
# Table 6: ten richest states 2020-21
STATES = {
    "Maharashtra": [2365, 14347, 8050, 2016, 588, 721, 661, 648],
    "Delhi": [14, 627, 2232, 594, 169, 209, 182, 181],
    "Gujarat": [1128, 8129, 4111, 877, 228, 239, 192, 141],
    "Tamil Nadu": [2483, 12017, 5827, 1181, 284, 279, 203, 137],
    "Punjab": [198, 2540, 2734, 589, 159, 168, 145, 101],
    "Karnataka": [1506, 7609, 5553, 973, 223, 203, 141, 91],
    "West Bengal": [4978, 12938, 5254, 909, 205, 189, 130, 88],
    "Uttar Pradesh": [6119, 22851, 10490, 1556, 324, 251, 165, 70],
    "Haryana": [136, 2342, 2626, 531, 136, 136, 112, 70],
    "Telangana": [977, 5074, 3227, 554, 122, 108, 72, 44],
}
# Table 7: ten richest cities 2020-21
CITIES = {
    "Mumbai": [27, 1210, 1864, 578, 183, 252, 241, 269],
    "Delhi": [12, 586, 2175, 582, 166, 206, 179, 180],
    "Pune": [7, 464, 620, 191, 60, 83, 79, 88],
    "Kolkata": [54, 1733, 1323, 316, 81, 88, 65, 52],
    "Chennai": [28, 703, 1353, 310, 77, 80, 57, 43],
    "Nagpur": [8, 209, 263, 82, 26, 36, 34, 39],
    "Ahmedabad": [19, 694, 614, 158, 43, 50, 40, 35],
    "Surat": [24, 831, 522, 135, 37, 43, 35, 31],
    "Nashik": [16, 205, 171, 54, 17, 24, 24, 27],
    "Bengaluru": [35, 1240, 1393, 294, 67, 62, 38, 24],
}
CITY_STATE = {"Mumbai": "Maharashtra", "Delhi": "Delhi", "Pune": "Maharashtra", "Kolkata": "West Bengal",
              "Chennai": "Tamil Nadu", "Nagpur": "Maharashtra", "Ahmedabad": "Gujarat", "Surat": "Gujarat",
              "Nashik": "Maharashtra", "Bengaluru": "Karnataka"}

# Hurun India Wealth Report 2025: millionaire households (net worth >= Rs 8.5 crore), top 10 cities
HURUN_2025 = {"Mumbai": 142000, "Delhi": 68200, "Bengaluru": 31600, "Ahmedabad": 26800, "Kolkata": 26600,
              "Chennai": 22800, "Pune": 22500, "Hyderabad": 19800, "Gurugram": 10100, "Surat": 5700}

# Official per-capita district income (Rs, current prices). measure, year and source differ, so shown with labels.
PER_CAPITA = {
    "Mumbai": (455767, "2023-24", "Per-capita NDDP, Mumbai city + suburban · Maharashtra Economic Survey 2024-25"),
    "Pune": (374257, "2023-24", "Per-capita NDDP · Maharashtra Economic Survey 2024-25"),
    "Nagpur": (322927, "2023-24", "Per-capita NDDP · Maharashtra Economic Survey 2024-25"),
    "Nashik": (249000, "2023-24", "Per-capita NDDP · Maharashtra Economic Survey 2024-25"),
    "Delhi": (457708, "2023-24", "Per-capita income · Economic Survey of Delhi 2025-26"),
    "Chennai": (646218, "2023-24", "Per-capita income, Chennai district · Tamil Nadu DES"),
    "Bengaluru": (780321, "2022-23", "Per-capita income, Bengaluru Urban · Karnataka DES"),
    "Ahmedabad": (654000, "2024-25", "Per-capita GDP, Ahmedabad district · secondary report of state estimate"),
    "Surat": (407000, "2024-25", "Per-capita GDP, Surat district · secondary report, low confidence"),
    "Kolkata": (246110, "2020-21", "Per-capita GDP, Kolkata district · older estimate"),
}

# PIB, 1 Aug 2024: ITRs filed for AY 2024-25 up to 31 July 2024, by form
ITR_FORMS_AY2024_25 = {
    "ITR-1 (salary, one house, other sources; income up to Rs 50L)": 33400000,
    "ITR-2 (salary + capital gains / more than one house)": 10900000,
    "ITR-3 (business or profession with books of account)": 9110000,
    "ITR-4 (presumptive business income, Sec 44AD/44ADA/44AE)": 18800000,
    "ITR-5 to ITR-7 (firms, trusts, others)": 748000,
}


def median_income(counts, q=0.5):
    """Interpolated quantile of household income (Rs lakh) from class counts."""
    total = sum(counts)
    target, c = q * total, 0.0
    for i, n in enumerate(counts):
        if c + n >= target:
            lo, hi = BOUNDS[i], BOUNDS[i + 1]
            u = (target - c) / n
            if hi is None:  # open class: Pareto with alpha 1.5
                return lo / (1 - u) ** (1 / 1.5) / 100
            if lo == 0:
                return hi * u / 100
            return lo * (hi / lo) ** u / 100
        c += n
    return None


def summarise(counts):
    total = sum(counts)
    grp = {}
    for cls, n in zip(CLASSES, counts):
        grp[GROUP[cls]] = grp.get(GROUP[cls], 0) + n
    return dict(
        households_k=total,
        classes_k=dict(zip(CLASSES, counts)),
        groups_k=grp,
        median_l=round(median_income(counts), 2),
        p25_l=round(median_income(counts, 0.25), 2),
        p75_l=round(median_income(counts, 0.75), 2),
        p90_l=round(median_income(counts, 0.90), 2),
        share_middle_plus=round(100 * sum(counts[2:]) / total, 1),   # >= Rs 5 lakh
        share_rich=round(100 * sum(counts[4:]) / total, 1),          # >= Rs 30 lakh
        rich_k=sum(counts[4:]),
        super_rich_k=counts[7],
    )


def main():
    out = dict(
        price_classes=[dict(name=c, group=GROUP[c], lo_k=BOUNDS[i], hi_k=BOUNDS[i + 1]) for i, c in enumerate(CLASSES)],
        india={y: summarise(v) for y, v in INDIA.items()},
        rural_urban={k: summarise(v) for k, v in RURAL_URBAN.items()},
        states={k: summarise(v) for k, v in STATES.items()},
        cities={k: summarise(v) | dict(
            state=CITY_STATE[k],
            hurun_2025=HURUN_2025.get(k),
            per_capita=dict(zip(("value", "year", "source"), PER_CAPITA[k])) if k in PER_CAPITA else None,
        ) for k, v in CITIES.items()},
        hurun_2025=HURUN_2025,
        itr_forms_ay2024_25=ITR_FORMS_AY2024_25,
        sources=dict(
            price="PRICE ICE 360 Surveys 2014/2016/2021 — 'The Rise of India's Middle Class', executive summary (price360.in)",
            hurun="Mercedes-Benz Hurun India Wealth Report 2025",
            pib="PIB, 'Record 7.28 crore ITRs filed for AY 2024-25 till 31st July, 2024'",
        ),
    )
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out["cities"].items():
        print(f"{k:10s} median ₹{v['median_l']:5.2f}L  middle+ {v['share_middle_plus']:5.1f}%  rich {v['share_rich']:4.1f}%  rich hh {v['rich_k']:4d}k")
    print("India 2020-21 median", out["india"]["2020-21"]["median_l"], "| urban", out["rural_urban"]["Urban"]["median_l"],
          "| rural", out["rural_urban"]["Rural"]["median_l"])


if __name__ == "__main__":
    main()
