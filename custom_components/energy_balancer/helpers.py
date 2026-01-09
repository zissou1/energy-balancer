from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # <-- add
import json
from statistics import mean
from typing import Any

from homeassistant.util import dt as dt_util


DEFAULT_SLOT_MS = 15 * 60 * 1000  # 15 minutes


@dataclass(frozen=True)
class Point:
    start_ts: int  # epoch ms (UTC)
    end_ts: int    # epoch ms (UTC)
    value: float


def _parse_raw(raw: Any) -> list[dict[str, Any]]:
    """raw_* can be list[dict] OR a JSON string."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except Exception:
            return []
    return []


def _to_ts_ms(v):
    """Convert ISO string OR datetime OR epoch to UTC epoch ms."""
    if v is None:
        return None

    # HA often gives datetime objects in attributes
    if isinstance(v, datetime):
        return int(dt_util.as_utc(v).timestamp() * 1000)

    # epoch seconds or ms
    if isinstance(v, (int, float)):
        n = float(v)
        if n > 10_000_000_000:  # already ms
            return int(n)
        return int(n * 1000)

    # ISO string
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        dt = dt_util.parse_datetime(s)
        if dt is None:
            return None
        return int(dt_util.as_utc(dt).timestamp() * 1000)

    return None


def normalize_raw_points(raw: Any) -> list[Point]:
    rows = _parse_raw(raw)
    out: list[Point] = []

    for r in rows:
        val = r.get("value", r.get("price"))
        if val is None:
            continue

        start_ts = r.get("start_ts")
        end_ts = r.get("end_ts")

        if start_ts is None:
            start_ts = _to_ts_ms(r.get("start"))
        else:
            start_ts = _to_ts_ms(start_ts)

        if end_ts is None:
            end_ts = _to_ts_ms(r.get("end"))
        else:
            end_ts = _to_ts_ms(end_ts)

        if start_ts is None or end_ts is None:
            continue

        try:
            fval = float(val)
        except Exception:
            continue

        out.append(Point(int(start_ts), int(end_ts), fval))

    out.sort(key=lambda p: p.start_ts)
    return out


def infer_slot_ms(points: list[Point]) -> int:
    if len(points) >= 2:
        d = points[1].start_ts - points[0].start_ts
        if 0 < d < 6 * 60 * 60 * 1000:
            return int(d)
    return DEFAULT_SLOT_MS


def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1:
        return values[:]
    out: list[float] = []
    half = window // 2
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(mean(values[lo:hi]))
    return out


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def quantize_step(x: float, step_size: float) -> float:
    if step_size <= 0:
        return x
    return round(x / step_size) * step_size
