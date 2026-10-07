"""
Jordan Labour Market 2017-2025 — data cleaning pipeline
Source: Department of Statistics (DoS) Jordan, Labour Force Survey databank
        https://jorinfo.dos.gov.jo/Databank/pxweb/ar/DOS_Database/START__12/

Input  (data/raw/):
    unemployed.xlsx  -> table EMPALL1 (Unemployed Jordanians 15+)
    employed.xlsx    -> table EMPALL  (Employed Jordanians 15+)
Output (data/processed/):
    jordan_labour_market_2017_2025.csv

Run:  python scripts/clean_data.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
YEARS = list(range(2017, 2026))
KEYS = ["gov", "sex", "marital", "age", "edu"]

# Official annual unemployment rates for Jordanians (DoS) used for validation
OFFICIAL_RATES = {2017: 18.3, 2019: 19.1, 2020: 23.2, 2021: 24.1}

GOV_EN = {
    "العاصمة": "Amman", "البلقاء": "Balqa", "الزرقاء": "Zarqa", "مادبا": "Madaba",
    "اربد": "Irbid", "المفرق": "Mafraq", "جرش": "Jerash", "عجلون": "Ajloun",
    "الكرك": "Karak", "الطفيلة": "Tafilah", "معان": "Maan", "العقبة": "Aqaba",
}
EDU = {  # arabic -> (order, english)
    "امي": (1, "Illiterate"), "ملم": (2, "Read & write"), "ابتدائي": (3, "Elementary"),
    "اعدادي": (4, "Preparatory"), "أساسي": (5, "Basic"),
    "تلمذة مهنية": (6, "Vocational apprenticeship"), "ثانوي": (7, "Secondary"),
    "دبلوم متوسط": (8, "Intermediate diploma"), "بكالوريوس فأعلى": (9, "Bachelor+"),
}
SEX = {"ذكر": "Male", "أنثى": "Female"}
MARITAL = {"أعزب": "Single", "متزوج / سبق لة الزواج": "Ever married"}
AGE = {"19-15": "15-19", "24-20": "20-24", "29-25": "25-29", "39-30": "30-39",
       "49-40": "40-49", "59-50": "50-59", "+60": "60+"}


def read_pxweb(path: Path, dims: list[str]) -> pd.DataFrame:
    """Read a PX-Web Excel export: skip title rows, drop metadata footer,
    forward-fill the blank (visually merged) dimension cells."""
    df = pd.read_excel(path, header=None, skiprows=3)
    df.columns = dims + YEARS
    df = df.loc[: df[dims[-1]].isna().idxmax() - 1].copy()   # stop at footer
    df[dims[:-1]] = df[dims[:-1]].ffill()
    df["edu"] = df["edu"].str.strip().str.replace("ـ", "", regex=False)
    df[YEARS] = df[YEARS].astype(float)
    return df


def to_long(df: pd.DataFrame, value: str) -> pd.DataFrame:
    wide = df.groupby(KEYS)[YEARS].sum()
    return wide.reset_index().melt(id_vars=KEYS, var_name="year", value_name=value)


def main() -> None:
    unemp = read_pxweb(RAW / "unemployed.xlsx", ["gov", "sex", "marital", "age", "edu", "work_exp"])
    emp = read_pxweb(RAW / "employed.xlsx", ["status", "gov", "sex", "marital", "age", "edu"])

    m = to_long(emp, "employed").merge(
        to_long(unemp, "unemployed"), on=KEYS + ["year"], how="outer", validate="1:1"
    )
    assert m.isna().sum().sum() == 0, "Employed/unemployed tables do not match"

    out = pd.DataFrame({
        "year": m["year"].astype(int),
        "governorate_ar": m["gov"],
        "governorate_en": m["gov"].map(GOV_EN),
        "sex": m["sex"].map(SEX),
        "marital_status": m["marital"].map(MARITAL),
        "age_group": m["age"].map(AGE),
        "education_ar": m["edu"],
        "education_en": m["edu"].map(lambda e: EDU[e][1]),
        "education_order": m["edu"].map(lambda e: EDU[e][0]),
        "employed": m["employed"].astype(int),
        "unemployed": m["unemployed"].astype(int),
    })
    out["labour_force"] = out["employed"] + out["unemployed"]
    assert out.isna().sum().sum() == 0, "Unmapped category found"

    # Validation against official DoS figures
    g = out.groupby("year")[["unemployed", "labour_force"]].sum()
    rates = (g["unemployed"] / g["labour_force"] * 100).round(1)
    for year, official in OFFICIAL_RATES.items():
        assert abs(rates[year] - official) <= 0.2, f"{year}: {rates[year]} vs official {official}"
    print("Unemployment rate by year (%):\n", rates.to_string())

    OUT.mkdir(parents=True, exist_ok=True)
    out.sort_values(["year", "governorate_en", "sex", "marital_status", "age_group", "education_order"]) \
       .to_csv(OUT / "jordan_labour_market_2017_2025.csv", index=False, encoding="utf-8-sig")
    print(f"Saved {len(out):,} rows -> {OUT / 'jordan_labour_market_2017_2025.csv'}")


if __name__ == "__main__":
    main()
