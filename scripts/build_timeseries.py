"""Macro series transcribed from CBDT 'Time Series Data FY 2000-01 to 2024-25' (released Nov 2025).

The tables in that PDF wrap across lines unpredictably, so the handful of series the
dashboard needs are transcribed here (page numbers refer to the PDF) and checked
against the PDF's own totals.  Output: data/processed/timeseries_*.csv
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
FY = ["2013-14", "2014-15", "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
      "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]


def lakh(s):
    return [float(x.replace(",", "")) for x in s.split("|")]


# p.2 / p.15  Direct tax collection (INR crore): corporate, non-corporate
corporate = lakh("3,94,678|4,28,925|4,53,228|4,84,924|5,71,202|6,63,572|5,56,876|4,57,719|7,12,037|8,25,834|9,11,055|9,86,767")
non_corp = lakh("2,42,888|2,65,772|2,87,637|3,49,503|4,20,084|4,73,179|4,92,717|4,87,560|6,96,604|8,33,307|10,44,726|12,35,161")
direct_total = lakh("6,38,596|6,95,792|7,41,945|8,49,713|10,02,738|11,37,718|10,50,681|9,47,176|14,12,422|16,63,686|19,60,166|22,26,375")
# p.6-7  GDP at current market prices (INR crore) and direct-tax/GDP ratio
gdp = lakh("1,13,55,073|1,25,41,208|1,35,67,192|1,53,62,386|1,70,98,304|1,88,86,957|2,00,74,856|1,98,29,927|2,35,97,399|2,68,90,473|3,01,22,956|3,30,68,145")
# p.12  Number of ITRs filed by individuals (incl. revised) in the financial year
itr_filed_ind = lakh("3,50,43,126|3,74,08,937|4,29,25,794|5,22,05,021|6,45,58,970|6,32,50,002|6,38,98,872|6,94,89,484|6,86,47,490|7,33,11,873|8,13,90,736|8,68,65,490")
# p.13  Number of individual persons filing ITR (return filers) in the financial year
filers_ind = lakh("3,04,97,487|3,23,72,285|3,61,38,618|4,15,93,816|5,09,89,970|5,95,44,767|6,11,30,366|6,31,71,013|6,54,61,868|6,96,90,925|7,63,70,510|8,08,80,773")
# p.14  Number of individual taxpayers (filed a return OR had TDS deducted) by AY 2013-14 .. 2024-25
taxpayers_ind = lakh("4,95,76,555|5,38,05,146|5,79,70,144|6,55,55,912|7,04,45,510|8,04,45,511|8,55,61,788|7,79,90,888|8,25,04,957|8,90,89,795|9,91,75,656|11,61,36,768")
AY = [f"{int(f[:4]) + 1}-{int(f[5:]) + 1:02d}" for f in FY]  # AY 2013-14 .. 2024-25

# World Bank WDI mid-year population (millions), calendar year = first year of FY. Approximate, for ratios only.
population_m = [1291.1, 1307.2, 1322.9, 1338.6, 1354.2, 1369.0, 1383.1, 1396.4, 1407.6, 1417.2, 1428.6, 1438.1]

# p.3-4  State/UT-wise direct tax collection (INR crore), FY 2018-19 .. 2024-25.
# Collections are attributed by the taxpayer's communication address, so HQ cities dominate.
STATE_FY = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
STATES = {
    "Maharashtra": ("Mumbai · Pune", "4,25,389.70|3,84,258.21|3,31,969.03|5,24,497.65|6,05,268.35|7,61,716.30|8,97,425.86"),
    "Karnataka": ("Bengaluru", "1,19,796.08|1,08,973.15|1,16,254.58|1,68,678.09|2,08,168.88|2,34,098.39|2,61,528.83"),
    "Delhi": ("Delhi", "1,66,404.99|1,49,613.12|1,20,120.94|1,77,824.22|2,21,522.20|2,03,197.06|2,29,250.33"),
    "Tamil Nadu": ("Chennai · Coimbatore", "74,238.70|69,809.31|61,122.33|88,438.33|1,07,063.82|1,27,067.17|1,32,368.09"),
    "Gujarat": ("Ahmedabad · Surat", "49,021.50|49,517.69|46,863.55|71,642.27|85,018.91|93,300.72|1,07,241.41"),
    "Telangana": ("Hyderabad", "10,860.20|14,045.81|15,853.93|27,184.95|35,433.56|84,439.24|97,860.86"),
    "Haryana": ("Gurugram", "29,881.15|27,824.12|24,492.81|37,729.33|45,649.85|70,947.31|79,731.48"),
    "Uttar Pradesh": ("Noida · Lucknow", "27,687.93|26,990.00|26,735.17|34,719.83|37,983.05|48,333.44|69,011.21"),
    "West Bengal": ("Kolkata", "44,638.58|40,628.71|40,310.24|53,774.61|55,560.62|60,374.64|63,075.47"),
    "Rajasthan": ("Jaipur", "21,059.38|16,507.93|17,539.35|25,215.64|30,609.56|30,551.42|34,382.78"),
    "Kerala": ("Kochi · Thiruvananthapuram", "17,021.10|15,164.10|14,515.59|19,562.02|23,983.26|23,966.92|27,974.60"),
    "Odisha": ("Bhubaneswar", "13,420.44|13,581.03|10,257.99|15,587.24|19,590.40|20,865.54|25,444.08"),
    "Andhra Pradesh": ("Visakhapatnam · Vijayawada", "46,222.64|42,730.45|40,314.07|56,663.27|57,324.09|26,066.46|23,804.85"),
    "Madhya Pradesh": ("Indore · Bhopal", "19,696.93|18,698.24|13,283.23|18,137.83|19,484.78|20,086.99|19,639.22"),
    "Punjab": ("Ludhiana · Mohali", "11,820.10|11,703.85|10,491.10|15,981.11|17,271.44|17,215.00|19,656.65"),
}
GRAND_TOTAL = lakh("11,37,718.48|10,50,680.56|9,47,176.37|14,12,422.45|16,63,686.47|19,61,823.56|22,26,374.94")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ts = pd.DataFrame(dict(fy=FY, ay=AY, corporate_tax_cr=corporate, non_corporate_tax_cr=non_corp,
                           direct_tax_cr=direct_total, gdp_cr=gdp, itr_filed_individual=itr_filed_ind,
                           return_filers_individual=filers_ind,
                           # p.14 is indexed by assessment year: taxpayers_ind[i] belongs to AY == FY[i]'s label
                           taxpayer_ay=FY, taxpayers_individual=taxpayers_ind,
                           population_m=population_m))
    assert all(abs(c + n - t) / t < 0.02 for c, n, t in zip(corporate, non_corp, direct_total)), "collection split (other direct taxes are <2%)"
    ts.to_csv(OUT / "timeseries_macro.csv", index=False)

    rows = []
    for st, (city, vals) in STATES.items():
        for fy, v in zip(STATE_FY, lakh(vals)):
            rows.append(dict(state=st, metro=city, fy=fy, direct_tax_cr=v))
    st = pd.DataFrame(rows)
    st = st.merge(pd.DataFrame(dict(fy=STATE_FY, india_total_cr=GRAND_TOTAL)), on="fy")
    st["share_pct"] = 100 * st.direct_tax_cr / st.india_total_cr
    st.to_csv(OUT / "timeseries_states.csv", index=False)
    print(ts.tail(3).T)
    print(st[st.fy == "2024-25"].sort_values("direct_tax_cr", ascending=False)[["state", "direct_tax_cr", "share_pct"]])


if __name__ == "__main__":
    main()
