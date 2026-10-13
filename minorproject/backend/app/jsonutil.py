"""Make pipeline output strictly JSON-safe (no NaN/inf, no numpy scalars)."""
from __future__ import annotations

import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(o, (pd.Timestamp, datetime, date)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if o is pd.NaT:
        return None
    return o


def dumps(o) -> str:
    return json.dumps(clean(o), default=str)
