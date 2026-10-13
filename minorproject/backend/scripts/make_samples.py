"""Generate the bundled demo datasets (seeded, reproducible).

These are SYNTHETIC datasets built to exercise every part of the pipeline —
trends, group differences, correlations, associations, anomalies, missing
values and duplicates. They are labelled as synthetic everywhere they appear.
For real data, upload a file or use the live feeds.

    python scripts/make_samples.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "samples"
rng = np.random.default_rng(2026)


def air_quality() -> pd.DataFrame:
    cities = {"Delhi": 118, "Kolkata": 72, "Mumbai": 54, "Chennai": 41, "Bengaluru": 38, "Hyderabad": 49}
    dates = pd.date_range("2023-01-01", "2025-06-30", freq="D")
    rows = []
    for city, base in cities.items():
        for i, d in enumerate(dates):
            winter = 1 + 0.55 * np.cos(2 * np.pi * (d.dayofyear - 10) / 365.25)
            trend = 1 - 0.00018 * i                      # slow improvement over time
            wind = max(0.5, rng.gamma(4, 2.2) * (0.8 if city == "Delhi" else 1.1))
            temp = 27 + (8 if city in ("Delhi",) else 3) * -np.cos(2 * np.pi * (d.dayofyear - 15) / 365.25) + rng.normal(0, 1.8)
            humidity = np.clip(62 + (12 if city in ("Mumbai", "Chennai", "Kolkata") else -6) + rng.normal(0, 9), 12, 100)
            pm25 = base * winter * trend * (1.35 - 0.035 * wind) * rng.lognormal(0, 0.22)
            if city == "Delhi" and d.month == 11 and d.day in (1, 2, 3) and d.year in (2023, 2024):
                pm25 *= 2.6                              # post-festival / stubble-burning spike
            no2 = 0.32 * pm25 + rng.normal(14, 6)
            rows.append({"date": d.date().isoformat(), "city": city, "pm25_ugm3": round(max(pm25, 3), 1),
                         "no2_ppb": round(max(no2, 2), 1), "temperature_c": round(temp, 1),
                         "humidity_pct": round(humidity, 1), "wind_speed_kmh": round(wind, 1)})
    df = pd.DataFrame(rows)
    df.loc[rng.choice(len(df), 120, replace=False), "no2_ppb"] = np.nan        # sensor gaps
    df.loc[rng.choice(len(df), 40, replace=False), "humidity_pct"] = np.nan
    df = pd.concat([df, df.sample(25, random_state=1)])                       # duplicate uploads
    return df.sample(frac=1, random_state=2).reset_index(drop=True)


def students() -> pd.DataFrame:
    n = 1400
    school = rng.choice(["Government", "Private", "Aided"], n, p=[0.48, 0.32, 0.20])
    gender = rng.choice(["Female", "Male"], n)
    internet = rng.choice(["Yes", "No"], n, p=[0.68, 0.32])
    parent = rng.choice(["School", "Graduate", "Postgraduate"], n, p=[0.45, 0.4, 0.15])
    study = np.clip(rng.gamma(3, 1.1, n) + (internet == "Yes") * 0.4, 0, 12)
    attendance = np.clip(rng.normal(82, 9, n) + (school == "Private") * 3, 35, 100)
    sleep = np.clip(rng.normal(7, 1.1, n) - 0.12 * study, 3.5, 10)
    screen = np.clip(rng.gamma(2.5, 1.3, n) + (internet == "Yes") * 1.2, 0, 14)
    score = (30 + 4.1 * study + 0.33 * attendance + 1.6 * (sleep - 7) - 1.1 * screen
             + (school == "Private") * 4.5 + (parent == "Postgraduate") * 3.5 + (parent == "Graduate") * 1.8
             + rng.normal(0, 7.5, n))
    score = np.clip(score, 0, 100)
    passed = np.where(score >= 50, "Pass", "Fail")
    df = pd.DataFrame({"student_id": np.arange(10001, 10001 + n), "school_type": school, "gender": gender,
                       "internet_access": internet, "parent_education": parent,
                       "study_hours_per_day": study.round(1), "attendance_pct": attendance.round(1),
                       "sleep_hours": sleep.round(1), "screen_time_hours": screen.round(1),
                       "final_score": score.round(1), "result": passed})
    df.loc[rng.choice(n, 60, replace=False), "sleep_hours"] = np.nan
    df.loc[[17, 401], "final_score"] = [4.0, 3.0]                              # suspicious entries
    return df


def retail() -> pd.DataFrame:
    months = pd.date_range("2021-01-01", "2025-06-01", freq="MS")
    regions = {"North": 1.0, "South": 1.18, "East": 0.82, "West": 1.07}
    cats = {"Electronics": 420, "Grocery": 610, "Apparel": 260, "Home": 190}
    rows = []
    for i, m in enumerate(months):
        festive = 1.35 if m.month in (10, 11) else 1.0
        for r, rm in regions.items():
            for c, base in cats.items():
                growth = 1 + 0.011 * i * (1.6 if c == "Electronics" else 1)
                promo = rng.random() < 0.25
                units = base * rm * growth * festive * (1.22 if promo else 1) * rng.lognormal(0, 0.12)
                price = {"Electronics": 310, "Grocery": 9, "Apparel": 28, "Home": 55}[c] * (0.9 if promo else 1) * rng.normal(1, 0.03)
                rows.append({"month": m.strftime("%Y-%m"), "region": r, "category": c,
                             "promotion": "Yes" if promo else "No", "units_sold": int(units),
                             "avg_price_usd": round(price, 2), "revenue_usd": round(units * price, 2),
                             "returns": int(units * rng.uniform(0.01, 0.05) * (1.8 if c == "Apparel" else 1))})
    df = pd.DataFrame(rows)
    df.loc[df.sample(1, random_state=5).index, "revenue_usd"] *= 9          # data-entry error
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    datasets = [
        ("air_quality", "Urban air quality — six Indian cities", air_quality(), "city_air_quality.csv",
         "Daily PM2.5, NO₂ and weather for six cities, Jan 2023 – Jun 2025. Includes sensor gaps and duplicate uploads."),
        ("students", "Student performance survey", students(), "student_performance.csv",
         "1,400 students: study habits, attendance, sleep, screen time and final exam scores."),
        ("retail", "Regional retail sales", retail(), "retail_sales.csv",
         "Monthly sales by region and category, 2021 – 2025, with promotions and returns."),
    ]
    index = []
    for sid, name, df, file, desc in datasets:
        df.to_csv(OUT / file, index=False)
        index.append({"id": sid, "name": name, "file": file, "rows": len(df), "cols": df.shape[1],
                      "description": desc + " Synthetic demonstration data (seeded generator).",
                      "synthetic": True})
        print(f"wrote {file}: {len(df):,} rows × {df.shape[1]} cols")
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
