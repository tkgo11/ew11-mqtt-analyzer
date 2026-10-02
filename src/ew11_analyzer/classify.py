"""Classify packet families as idle (periodic baseline) vs event-driven.

The core question the tool answers: "which packets are always on the bus,
and which appear only when I press a button?"

Method:
- Periodicity: coefficient of variation (cv = std/mean) of inter-arrival
  intervals. Wallpad polling / status broadcasts are extremely regular.
- Event lift: compare the family's arrival rate inside marker windows
  vs outside. A family that only fires near markers has lift >> 1.
- Baseline presence: fraction of occurrences outside any marker window.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import pairwise
from typing import Any


@dataclass
class Marker:
    id: int
    ts: float
    label: str


@dataclass
class FamilyVerdict:
    sig: str
    count: int
    rate_per_min: float
    mean_interval: float | None
    cv: float | None
    periodicity: float  # 0..1, 1 = perfectly regular
    baseline_count: int
    event_count: int
    event_lift: float | None  # rate inside marker windows / outside
    marker_ids: list[int]
    verdict: str  # IDLE | EVENT | MIXED | UNKNOWN
    verdict_ko: str
    confidence: float
    topics: list[str]
    first_ts: float
    last_ts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sig": self.sig,
            "count": self.count,
            "rate_per_min": round(self.rate_per_min, 2),
            "mean_interval": round(self.mean_interval, 4) if self.mean_interval is not None else None,
            "cv": round(self.cv, 4) if self.cv is not None else None,
            "periodicity": round(self.periodicity, 4),
            "baseline_count": self.baseline_count,
            "event_count": self.event_count,
            "event_lift": round(self.event_lift, 3) if self.event_lift is not None else None,
            "marker_ids": self.marker_ids,
            "verdict": self.verdict,
            "verdict_ko": self.verdict_ko,
            "confidence": round(self.confidence, 3),
            "topics": self.topics,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
        }


VERDICT_KO = {
    "IDLE": "주기 신호",
    "EVENT": "이벤트",
    "MIXED": "혼합",
    "UNKNOWN": "미분류",
}


def _merged_windows(markers: list[Marker], pre: float, post: float) -> list[tuple[float, float]]:
    windows = sorted((m.ts - pre, m.ts + post) for m in markers)
    merged: list[list[float]] = []
    for a, b in windows:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def _count_in_windows(timestamps: list[float], windows: list[tuple[float, float]]) -> int:
    if not windows:
        return 0
    count = 0
    wi = 0
    for ts in timestamps:
        while wi < len(windows) and ts > windows[wi][1]:
            wi += 1
        if wi >= len(windows):
            break
        if windows[wi][0] <= ts <= windows[wi][1]:
            count += 1
    return count


def _periodicity(ts: list[float]) -> tuple[float | None, float | None, float]:
    """Return (mean_interval, cv, periodicity 0..1)."""
    intervals = [b - a for a, b in pairwise(ts)]
    mean_interval = statistics.fmean(intervals) if intervals else None
    if len(intervals) >= 2 and mean_interval and mean_interval > 0:
        cv = statistics.pstdev(intervals) / mean_interval
        return mean_interval, cv, max(0.0, 1.0 - min(cv, 1.0))
    return mean_interval, None, 0.0


def _window_stats(
    ts: list[float],
    windows: list[tuple[float, float]],
    duration: float,
) -> tuple[int, int, float | None]:
    """Return (event_count, baseline_count, event_lift)."""
    count = len(ts)
    if not windows:
        return 0, count, None
    event_time = min(sum(b - a for a, b in windows), duration)
    base_time = duration - event_time
    event_count = _count_in_windows(ts, windows)
    baseline_count = count - event_count
    if event_time <= 0 or base_time <= 0:
        return event_count, baseline_count, None
    out_rate = baseline_count / base_time
    if event_count > 0 and out_rate <= 0:
        return event_count, baseline_count, 99.0
    in_rate = event_count / event_time if event_time > 0 else 0.0
    return event_count, baseline_count, in_rate / out_rate if out_rate > 0 else 0.0


def _decide(
    count: int,
    *,
    event_frac: float,
    base_frac: float,
    event_lift: float | None,
    periodicity: float,
    has_markers: bool,
    event_count: int,
) -> tuple[str, float]:
    verdict, confidence = "MIXED", 0.45
    if count < 3 or (has_markers and event_lift is None):
        # a packet that only ever appears inside marker windows is a command
        # candidate even with a single observation
        if has_markers and event_lift is not None and event_count > 0 and base_frac == 0.0:
            verdict, confidence = "EVENT", min(0.7, 0.35 + 0.15 * event_count)
        else:
            verdict, confidence = "UNKNOWN", 0.2
    elif not has_markers:
        if periodicity >= 0.7:
            verdict = "IDLE"
            confidence = min(0.9, 0.5 + 0.05 * min(count // 20, 6))
        else:
            verdict, confidence = "UNKNOWN", 0.35
    elif event_lift is not None and event_lift >= 3.0:
        if event_frac >= 0.25:
            verdict = "EVENT"
            confidence = min(0.95, 0.55 + 0.08 * min(event_count, 5))
        else:
            verdict, confidence = "MIXED", 0.5
    elif periodicity >= 0.65:
        verdict = "IDLE"
        confidence = min(0.95, 0.6 + 0.05 * min(count // 20, 6))
    elif event_lift is not None and event_lift >= 2.0:
        verdict, confidence = "MIXED", 0.55
    elif base_frac >= 0.7:
        verdict, confidence = "IDLE", 0.6
    return verdict, confidence


def classify_family(
    sig: str,
    timestamps: list[float],
    topics: list[str],
    *,
    markers: list[Marker],
    start: float,
    end: float,
    pre: float = 0.3,
    post: float = 1.5,
) -> FamilyVerdict:
    ts = sorted(timestamps)
    count = len(ts)
    duration = max(end - start, 0.0)
    rate_per_min = count / duration * 60.0 if duration > 0 else 0.0

    mean_interval, cv, periodicity = _periodicity(ts)
    windows = [
        (max(a, start), min(b, end))
        for a, b in _merged_windows(markers, pre, post)
        if a <= end and b >= start
    ]
    event_count, baseline_count, event_lift = _window_stats(ts, windows, duration)
    marker_ids = [m.id for m in markers if _count_in_windows(ts, [(m.ts - pre, m.ts + post)]) > 0]

    verdict, confidence = _decide(
        count,
        event_frac=event_count / count if count else 0.0,
        base_frac=baseline_count / count if count else 0.0,
        event_lift=event_lift,
        periodicity=periodicity,
        has_markers=bool(windows),
        event_count=event_count,
    )

    return FamilyVerdict(
        sig=sig,
        count=count,
        rate_per_min=rate_per_min,
        mean_interval=mean_interval,
        cv=cv,
        periodicity=periodicity,
        baseline_count=baseline_count,
        event_count=event_count,
        event_lift=event_lift,
        marker_ids=marker_ids,
        verdict=verdict,
        verdict_ko=VERDICT_KO[verdict],
        confidence=confidence,
        topics=sorted(set(topics)),
        first_ts=ts[0] if ts else 0.0,
        last_ts=ts[-1] if ts else 0.0,
    )
