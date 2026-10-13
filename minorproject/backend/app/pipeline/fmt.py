"""Human-friendly number formatting shared by the narrative and the report."""
from __future__ import annotations

import math
import re


def num(v, digits: int = 3) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "n/a"
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.2f} billion"
    if a >= 1e6:
        return f"{v / 1e6:.2f} million"
    if a >= 1e4:
        return f"{v:,.0f}"
    if a >= 100:
        return f"{v:,.1f}".rstrip("0").rstrip(".")
    if a == 0:
        return "0"
    if float(v).is_integer():
        return f"{int(v)}"
    if a >= 1:
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:.{digits}g}"


def pct(v, signed: bool = False) -> str:
    if v is None:
        return "n/a"
    s = f"{v:+.1f}%" if signed else f"{v:.1f}%"
    return s.replace(".0%", "%")


def pval(p) -> str:
    if p is None:
        return "p = n/a"
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.3f}"


UNITS = {
    "pct": "%", "percent": "%", "c": "°C", "f": "°F", "kmh": "km/h", "mph": "mph", "usd": "USD",
    "inr": "INR", "eur": "EUR", "ugm3": "µg/m³", "ppb": "ppb", "ppm": "ppm", "mm": "mm", "cm": "cm",
    "km": "km", "kg": "kg", "hpa": "hPa", "ms": "ms", "s": "s", "hrs": "hours", "hours": "hours",
}
ACRONYMS = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO₂", "so2": "SO₂", "co2": "CO₂", "o3": "O₃",
            "gdp": "GDP", "usd": "USD", "id": "ID", "aqi": "AQI", "cpi": "CPI", "bmi": "BMI", "kpi": "KPI"}


def _split_unit(col: str) -> tuple[list[str], str | None]:
    words = [w for w in re.split(r"[_\-\s]+", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(col)).strip()) if w]
    unit = None
    if len(words) > 1 and words[-1].lower() in UNITS:
        unit = UNITS[words[-1].lower()]
        words = words[:-1]
    return words, unit


def humanize(col: str) -> str:
    """Prose name without unit suffix: 'pm25_ugm3' → 'PM2.5', 'attendance_pct' → 'attendance'."""
    words, _ = _split_unit(col)
    out = [ACRONYMS.get(w.lower(), w if w.isupper() and len(w) > 1 else w.lower()) for w in words]
    return " ".join(out) or str(col)


def title(col: str) -> str:
    h = humanize(col)
    return h[:1].upper() + h[1:]


def label(col: str) -> str:
    """Axis label with unit: 'temperature_c' → 'Temperature (°C)'."""
    _, unit = _split_unit(col)
    return f"{title(col)} ({unit})" if unit else title(col)


def date(iso: str, unit: str = "day") -> str:
    from datetime import datetime
    try:
        d = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    if unit == "year":
        return f"{d.year}"
    if unit in ("quarter",):
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    if unit == "month":
        return d.strftime("%B %Y")
    if unit == "hour":
        return d.strftime("%d %b %Y, %H:00")
    return d.strftime("%d %b %Y").lstrip("0")


def when(iso: str, unit: str = "day") -> str:
    """'on 3 Nov 2024' / 'in 2020' / 'in March 2024' — the right preposition for the period."""
    prep = "in" if unit in ("year", "quarter", "month", "week") else ("at" if unit == "hour" else "on")
    if unit == "week":
        return f"in the week of {date(iso, 'day')}"
    return f"{prep} {date(iso, unit)}"
