"""Event-window diffing: find what changed when a button was pressed.

For each marker we collect packets inside its window and compare them with
the baseline (packets of the same family outside all marker windows). A
family that is novel (never seen in baseline) or whose bytes change at
specific positions is a strong command/response candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .classify import Marker, _merged_windows
from .families import signature
from .packets import Packet


@dataclass
class FamilyDiff:
    sig: str
    count_in: int
    novel: bool
    changed_positions: list[int]
    samples_in: list[str]  # hex payloads inside the window
    samples_out: list[str]  # baseline samples (up to 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sig": self.sig,
            "count_in": self.count_in,
            "novel": self.novel,
            "changed_positions": self.changed_positions,
            "samples_in": self.samples_in,
            "samples_out": self.samples_out,
        }


@dataclass
class MarkerDiff:
    marker: Marker
    hits: list[FamilyDiff] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker": {"id": self.marker.id, "ts": self.marker.ts, "label": self.marker.label},
            "hits": [h.to_dict() for h in self.hits],
        }


def _byte_values(packets: list[Packet]) -> list[set[int]]:
    values: list[set[int]] = [set() for _ in packets[0].payload] if packets else []
    for packet in packets:
        for i, value in enumerate(packet.payload):
            values[i].add(value)
    return values


def _positions_changed(packets: list[Packet], baseline: list[set[int]]) -> list[int]:
    """Byte positions where any in-window value leaves the baseline value set."""
    return [i for i, values in enumerate(baseline) if any(p.payload[i] not in values for p in packets)]


def diff_around_markers(
    packets: list[Packet],
    markers: list[Marker],
    *,
    pre: float = 0.3,
    post: float = 1.5,
    prefix_len: int = 3,
) -> list[MarkerDiff]:
    windows = _merged_windows(markers, pre, post)

    baseline_by_sig: dict[str, list[Packet]] = {}
    in_window: list[tuple[float, Packet]] = []
    for p in packets:
        sig = signature(p.payload, prefix_len)
        inside = any(a <= p.ts <= b for a, b in windows)
        if inside:
            in_window.append((p.ts, p))
        else:
            baseline_by_sig.setdefault(sig, []).append(p)

    baseline_values = {sig: _byte_values(pkts) for sig, pkts in baseline_by_sig.items()}
    diffs: list[MarkerDiff] = []
    for m in markers:
        md = MarkerDiff(marker=m)
        per_sig: dict[str, list[Packet]] = {}
        for ts, p in in_window:
            if m.ts - pre <= ts <= m.ts + post:
                per_sig.setdefault(signature(p.payload, prefix_len), []).append(p)
        for sig, pkts in sorted(per_sig.items(), key=lambda kv: -len(kv[1])):
            base = baseline_by_sig.get(sig, [])
            changed = _positions_changed(pkts, baseline_values.get(sig, []))
            novel = len(base) == 0
            # keep the interesting ones on top: novel > changed > rest
            md.hits.append(
                FamilyDiff(
                    sig=sig,
                    count_in=len(pkts),
                    novel=novel,
                    changed_positions=changed,
                    samples_in=[p.hex for p in pkts[:6]],
                    samples_out=[p.hex for p in base[:4]],
                )
            )
        md.hits.sort(key=lambda h: (not h.novel, -len(h.changed_positions), -h.count_in))
        diffs.append(md)
    return diffs
