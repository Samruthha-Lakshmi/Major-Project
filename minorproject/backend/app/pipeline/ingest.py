"""Stage 1 — data ingestion and schema validation.

Loads CSV / TSV / Excel / JSON bytes into a DataFrame and infers a semantic type
for every column (numeric, datetime, categorical, boolean, text, identifier).
"""
from __future__ import annotations

import csv
import io
import json
import re
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import MAX_ROWS


class IngestError(ValueError):
    """Raised when a dataset cannot be loaded or is unusable."""


@dataclass
class ColumnSchema:
    name: str
    semantic: str          # numeric | datetime | categorical | boolean | text | id
    dtype: str
    non_null: int
    missing: int
    unique: int
    sample: list = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


_NUM_CLEAN = re.compile(r"[,\s$€£₹%]")
_ID_NAME = re.compile(r"(^id$|_id$|^id_|uuid|identifier|^code$|^key$)", re.I)
_YEAR_NAME = re.compile(r"^(year|yr|fiscal_year|season)$", re.I)
_DATE_NAME = re.compile(r"(date|time|month|day|period|timestamp)", re.I)


# ---------------------------------------------------------------------------- loading
def load_bytes(filename: str, data: bytes) -> pd.DataFrame:
    name = filename.lower()
    if not data:
        raise IngestError("The uploaded file is empty.")
    try:
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            df = pd.read_excel(io.BytesIO(data))
        elif name.endswith((".json", ".geojson")):
            df = _load_json(data)
        else:
            df = _load_delimited(data, tab=name.endswith(".tsv"))
    except IngestError:
        raise
    except Exception as exc:  # pandas raises many types; surface one readable message
        raise IngestError(f"Could not parse {filename}: {exc}") from exc
    return finalize(df)


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or df.shape[1] == 0:
        raise IngestError("The dataset has no rows or no columns.")
    if len(df) > MAX_ROWS:
        df = df.sample(MAX_ROWS, random_state=7).sort_index()
    df.columns = _dedupe([_clean_name(c) for c in df.columns])
    return df


def _load_delimited(data: bytes, tab: bool) -> pd.DataFrame:
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise IngestError("Unrecognised text encoding.")
    sep = "\t" if tab else None
    if sep is None:
        try:
            sep = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
        except csv.Error:
            sep = ","
    return pd.read_csv(io.StringIO(text), sep=sep, low_memory=False)


def _load_json(data: bytes) -> pd.DataFrame:
    obj = json.loads(data.decode("utf-8-sig"))
    if isinstance(obj, dict):
        if obj.get("type") == "FeatureCollection":
            return pd.json_normalize([f.get("properties", {}) for f in obj.get("features", [])])
        for key in ("data", "records", "rows", "items", "results"):
            if isinstance(obj.get(key), list):
                obj = obj[key]
                break
    if not isinstance(obj, list):
        raise IngestError("JSON must be an array of records (or contain one under 'data').")
    return pd.json_normalize(obj)


def _clean_name(c) -> str:
    s = str(c).strip()
    s = re.sub(r"\s+", " ", s)
    return s or "column"


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
        else:
            seen[n] = 0
            out.append(n)
    return out


# ---------------------------------------------------------------------------- typing
def _try_numeric(s: pd.Series) -> pd.Series | None:
    if pd.api.types.is_bool_dtype(s):
        return None
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    nn = s.dropna().astype(str)
    if nn.empty:
        return None
    cleaned = nn.str.replace(_NUM_CLEAN, "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    if parsed.notna().mean() >= 0.95:
        full = pd.to_numeric(s.astype(str).str.replace(_NUM_CLEAN, "", regex=True), errors="coerce")
        return full.where(s.notna())
    return None


def _try_datetime(s: pd.Series, name: str) -> pd.Series | None:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    if pd.api.types.is_numeric_dtype(s):
        return None
    nn = s.dropna().astype(str)
    if nn.empty or nn.str.len().median() < 6:
        return None
    # Pure numbers are not dates unless the column name says so.
    if nn.str.fullmatch(r"-?\d+(\.\d+)?").mean() > 0.5 and not _DATE_NAME.search(name):
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(s, errors="coerce", utc=True)
    if parsed.notna().sum() >= 0.9 * s.notna().sum():
        return parsed.dt.tz_convert(None)
    return None


def infer_schema(df: pd.DataFrame) -> tuple[pd.DataFrame, list[ColumnSchema]]:
    """Return a type-coerced copy of *df* plus the inferred schema."""
    out = df.copy()
    schema: list[ColumnSchema] = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        if s.dtype == object:
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v).replace({"": np.nan})
        semantic, note = "text", ""
        lowered = s.dropna().astype(str).str.lower()
        bool_vals = {"true", "false", "yes", "no", "y", "n", "0", "1", "t", "f"}

        num = _try_numeric(s)
        if pd.api.types.is_bool_dtype(s) or (not lowered.empty and lowered.nunique() <= 2
                                             and set(lowered.unique()) <= bool_vals
                                             and lowered.nunique() == 2):
            # Keep the original wording ("Yes"/"No", "True"/"False") — it reads better in the story.
            semantic = "boolean"
            s = s.map(lambda v: v if pd.isna(v) else str(v).strip().title()
                      if not isinstance(v, (bool, np.bool_)) else ("Yes" if v else "No"))
        elif num is not None:
            nunique = num.nunique()
            ints = bool((num.dropna() % 1 == 0).all())
            if _YEAR_NAME.match(str(col)) and ints and num.dropna().between(1800, 2200).all():
                semantic, note = "datetime", "year"
                s = pd.to_datetime(num.astype("Int64").astype(str), format="%Y", errors="coerce")
            elif _ID_NAME.search(str(col)) and nunique >= 0.95 * num.notna().sum():
                semantic, s = "id", num
            elif ints and nunique <= 2 and set(num.dropna().unique()) <= {0, 1}:
                semantic, s = "boolean", num.map({1: "Yes", 0: "No"}).astype(object).where(num.notna())
            elif ints and nunique <= 12 and n >= 40 and not _looks_measure(str(col)):
                semantic, s = "categorical", num.astype("Int64").astype(str).where(num.notna())
                note = "low-cardinality integer treated as category"
            else:
                semantic, s = "numeric", num
        else:
            dt = _try_datetime(s, str(col))
            if dt is not None:
                semantic, s = "datetime", dt
            else:
                nn = s.dropna().astype(str)
                nunique = nn.nunique()
                avg_len = nn.str.len().mean() if not nn.empty else 0
                if nunique == 0:
                    semantic, note = "text", "empty column"
                elif _ID_NAME.search(str(col)) or (nunique >= 0.98 * len(nn) and avg_len < 40 and len(nn) > 50):
                    semantic = "id"
                elif avg_len > 40 and nunique > 0.5 * len(nn):
                    semantic = "text"
                elif nunique <= max(30, int(0.05 * n)) or nunique / max(len(nn), 1) < 0.5:
                    semantic = "categorical"
                else:
                    semantic = "text"
        out[col] = s
        nn_vals = s.dropna()
        schema.append(ColumnSchema(
            name=str(col), semantic=semantic, dtype=str(s.dtype),
            non_null=int(nn_vals.size), missing=int(n - nn_vals.size),
            unique=int(nn_vals.astype(str).nunique()),
            sample=[_jsonable(v) for v in nn_vals.head(3).tolist()],
            note=note))
    return out, schema


def _looks_measure(name: str) -> bool:
    return bool(re.search(r"(count|total|amount|score|rate|age|price|value|qty|quantity|number|num_|sales|deaths|cases|pop)", name, re.I))


def _jsonable(v):
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def validate(df: pd.DataFrame, schema: list[ColumnSchema]) -> list[dict]:
    """Return a list of validation issues ({level, message}) — never raises for soft issues."""
    issues: list[dict] = []
    n = len(df)
    if n < 10:
        issues.append({"level": "error", "message": f"Only {n} rows — at least 10 are needed for statistics."})
    analysable = [c for c in schema if c.semantic in ("numeric", "categorical", "boolean", "datetime")]
    if not any(c.semantic == "numeric" for c in schema):
        issues.append({"level": "warning", "message": "No numeric measures found — analysis will be limited to categorical associations."})
    if len(analysable) < 2:
        issues.append({"level": "warning", "message": "Fewer than two analysable columns — few relationships can be tested."})
    for c in schema:
        frac = c.missing / n if n else 0
        if c.note == "empty column":
            issues.append({"level": "warning", "message": f"Column '{c.name}' is entirely empty and will be dropped."})
        elif frac > 0.5:
            issues.append({"level": "warning", "message": f"Column '{c.name}' is {frac:.0%} missing."})
        elif c.unique == 1 and c.non_null > 0:
            issues.append({"level": "info", "message": f"Column '{c.name}' is constant and carries no information."})
    return issues
