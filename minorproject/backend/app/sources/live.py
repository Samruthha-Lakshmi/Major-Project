"""Real-time public data feeds (no API keys required).

* USGS earthquake feed — every earthquake recorded worldwide in the last day / week / month
* Open-Meteo — hourly weather observations and forecast for a city
* World Bank — development indicators for a set of countries over decades
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pandas as pd

TIMEOUT = httpx.Timeout(45.0, connect=10.0)
UA = {"User-Agent": "AutomatedDataJournalismPipeline/1.0 (academic project)"}

CITIES = {
    "chennai": ("Chennai", 13.0827, 80.2707),
    "delhi": ("New Delhi", 28.6139, 77.2090),
    "mumbai": ("Mumbai", 19.0760, 72.8777),
    "bengaluru": ("Bengaluru", 12.9716, 77.5946),
    "london": ("London", 51.5072, -0.1276),
    "new_york": ("New York", 40.7128, -74.0060),
    "tokyo": ("Tokyo", 35.6762, 139.6503),
}

WB_INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
    "SP.DYN.LE00.IN": "Life expectancy at birth (years)",
    "EN.GHG.CO2.PC.CE.AR5": "CO2 emissions per capita (t CO2e)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total)",
    "IT.NET.USER.ZS": "Internet users (% of population)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
}
WB_COUNTRIES = "IND;CHN;USA;BRA;ZAF;GBR;JPN;DEU;NGA;IDN;BGD;MEX"

SOURCES = [
    {
        "id": "usgs", "name": "USGS Earthquakes", "refreshable": True,
        "description": "Every earthquake recorded worldwide by the US Geological Survey, updated every minute.",
        "params": [{"name": "window", "label": "Window", "options": ["day", "week", "month"], "default": "week"},
                   {"name": "min_mag", "label": "Minimum magnitude", "options": ["all", "1.0", "2.5", "4.5"], "default": "all"}],
    },
    {
        "id": "weather", "name": "Open-Meteo Weather", "refreshable": True,
        "description": "Hourly temperature, humidity, rain, wind and pressure — past 14 days plus 2-day forecast.",
        "params": [{"name": "city", "label": "City", "options": list(CITIES), "default": "chennai"}],
    },
    {
        "id": "worldbank", "name": "World Bank Indicators", "refreshable": False,
        "description": "Development indicators for 12 major economies since 1990.",
        "params": [{"name": "indicator", "label": "Indicator", "options": list(WB_INDICATORS),
                    "labels": WB_INDICATORS, "default": "NY.GDP.MKTP.KD.ZG"}],
    },
]


class SourceError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, attempts: int = 2):
    for attempt in range(attempts):
        try:
            r = httpx.get(url, params=params, timeout=TIMEOUT, headers=UA, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            if attempt == attempts - 1:
                raise SourceError(f"Could not reach {url.split('/')[2]} ({type(exc).__name__}). "
                                  "The public feed may be slow or offline - try again shortly.") from exc


def fetch(source_id: str, params: dict, log=lambda *_: None) -> tuple[pd.DataFrame, dict]:
    if source_id == "usgs":
        return _usgs(params, log)
    if source_id == "weather":
        return _weather(params, log)
    if source_id == "worldbank":
        return _worldbank(params, log)
    raise SourceError(f"Unknown live source '{source_id}'")


def _usgs(params: dict, log):
    window = params.get("window", "week")
    mag = {"all": "all", "1.0": "1.0", "2.5": "2.5", "4.5": "4.5"}.get(str(params.get("min_mag", "all")), "all")
    url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{mag}_{window}.geojson"
    log(f"GET {url}")
    data = _get(url)
    rows = []
    for f in data.get("features", []):
        p, g = f["properties"], f["geometry"]["coordinates"]
        place = p.get("place") or ""
        region = place.split(", ")[-1].strip() if ", " in place else (place.split(" of ")[-1].strip() or "Unknown")
        # Only reader-relevant fields: catalogue metadata (magnitude type, network, review status,
        # USGS's derived 'sig' score, raw coordinates) yields valid but meaningless "findings".
        rows.append({
            "time": datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).replace(tzinfo=None),
            "magnitude": p.get("mag"), "depth_km": g[2] if len(g) > 2 else None,
            "region": region, "place": place, "event_type": p.get("type"),
            "felt_reports": p.get("felt"), "tsunami_warning": p.get("tsunami"),
        })
    if not rows:
        raise SourceError("The USGS feed returned no events for this window.")
    df = pd.DataFrame(rows)
    # Keep the regions table readable: rare regions grouped as "Other".
    top = df["region"].value_counts()
    df["region_group"] = df["region"].where(df["region"].isin(top.head(10).index), "Other")
    meta = data.get("metadata", {})
    log(f"USGS feed generated {datetime.fromtimestamp(meta.get('generated', 0) / 1000, tz=timezone.utc):%Y-%m-%d %H:%M} UTC")
    return df, {"type": "live", "id": "usgs", "name": f"USGS earthquake feed (past {window})",
                "url": "https://earthquake.usgs.gov/earthquakes/feed/",
                "description": f"Earthquakes worldwide in the past {window}, magnitude ≥ {mag}.",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _weather(params: dict, log):
    key = params.get("city", "chennai")
    name, lat, lon = CITIES.get(key, CITIES["chennai"])
    url = "https://api.open-meteo.com/v1/forecast"
    q = {"latitude": lat, "longitude": lon, "past_days": 14, "forecast_days": 2, "timezone": "auto",
         "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
                   "cloud_cover,wind_speed_10m,surface_pressure"}
    log(f"GET {url} for {name}")
    data = _get(url, q)
    h = data["hourly"]
    df = pd.DataFrame(h).rename(columns={
        "temperature_2m": "temperature_c", "relative_humidity_2m": "humidity_pct",
        "apparent_temperature": "feels_like_c", "precipitation": "rain_mm", "cloud_cover": "cloud_cover_pct",
        "wind_speed_10m": "wind_kmh", "surface_pressure": "pressure_hpa"})
    df["time"] = pd.to_datetime(df["time"])
    now = pd.Timestamp.now(tz=data.get("timezone") or "UTC").tz_localize(None)
    df["period"] = (df["time"] > now).map({True: "forecast", False: "observed"})
    df["part_of_day"] = pd.cut(df["time"].dt.hour, bins=[-1, 5, 11, 17, 23],
                               labels=["night", "morning", "afternoon", "evening"]).astype(str)
    return df, {"type": "live", "id": "weather", "name": f"Open-Meteo weather — {name}",
                "url": "https://open-meteo.com/",
                "description": f"Hourly weather for {name}: 14 days observed plus a 2-day forecast.",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _worldbank(params: dict, log):
    ind = params.get("indicator", "NY.GDP.MKTP.KD.ZG")
    label = WB_INDICATORS.get(ind, ind)
    # Per-country and multi-country queries of this API frequently hang; the all-countries
    # response is cached upstream and fast, so fetch it once and filter locally.
    # Query string kept literal: the upstream cache keys on the unencoded "1990:2025".
    url = f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&date=1990:2025"
    log(f"GET {url}")
    data = _get(url)
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        raise SourceError("World Bank API returned no data for this indicator.")
    wanted = set(WB_COUNTRIES.split(";"))
    recs = [r for r in data[1] if r.get("countryiso3code") in wanted]
    rows = [{"country": r["country"]["value"], "year": int(r["date"]), "value": r["value"]}
            for r in recs if r.get("value") is not None]
    if not rows:
        raise SourceError("World Bank API returned no data for this indicator.")
    df = pd.DataFrame(rows).sort_values(["country", "year"])
    col = "".join(ch if ch.isalnum() else "_" for ch in label.split("(")[0].strip().lower()).strip("_")
    df = df.rename(columns={"value": col})
    df["decade"] = (df["year"] // 10 * 10).astype(str) + "s"
    return df, {"type": "live", "id": "worldbank", "name": f"World Bank — {label}",
                "url": f"https://data.worldbank.org/indicator/{ind}",
                "description": f"{label} for 12 economies, 1990 onwards.",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
