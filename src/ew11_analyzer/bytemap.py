"""Per-byte variance analysis within a packet family.

For every byte position we compute distinct-value count, Shannon entropy,
the most common values, and a role guess:

- ``header``: constant byte inside the signature prefix
- ``const``: constant byte elsewhere (device address, fixed command)
- ``tail``: constant last byte (ETX)
- ``checksum``: position identified by checksum detection
- ``counter``: value increments by 1 (mod 256) between consecutive samples
- ``state``: small number of distinct values (flags / state field)
- ``data``: high-variance payload byte
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from typing import Any


@dataclass
class ByteStat:
    idx: int
    distinct: int
    entropy: float
    top: list[tuple[int, int]]  # (byte value, count)
    role: str = "data"
    const_val: int | None = None
    is_counter: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "idx": self.idx,
            "distinct": self.distinct,
            "entropy": round(self.entropy, 3),
            "top": [[f"{v:02X}", c] for v, c in self.top],
            "role": self.role,
            "const": self.const_val,
            "is_counter": self.is_counter,
        }


def _entropy(counts: Counter[int], total: int) -> float:
    e = 0.0
    for c in counts.values():
        p = c / total
        e -= p * math.log2(p)
    return e


def _is_counter(vals: list[int]) -> bool:
    if len(vals) < 4:
        return False
    inc = sum(1 for a, b in pairwise(vals) if (b - a) % 256 == 1)
    return inc / (len(vals) - 1) >= 0.8 and len(set(vals)) > 2


def byte_map(
    samples: list[bytes],
    checksum_positions: set[int] | None = None,
    prefix_len: int = 2,
    max_samples: int = 256,
) -> list[ByteStat]:
    samples = samples[:max_samples]
    if not samples:
        return []
    n = len(samples[0])
    checksum_positions = checksum_positions or set()
    stats: list[ByteStat] = []
    for i in range(n):
        vals = [s[i] for s in samples]
        counts = Counter(vals)
        distinct = len(counts)
        st = ByteStat(
            idx=i,
            distinct=distinct,
            entropy=_entropy(counts, len(vals)),
            top=counts.most_common(5),
        )
        if distinct == 1:
            st.const_val = vals[0]
        st.is_counter = _is_counter(vals)

        if i in checksum_positions:
            st.role = "checksum"
        elif i < prefix_len and distinct == 1:
            st.role = "header"
        elif i == n - 1 and distinct == 1:
            st.role = "tail"
        elif distinct == 1:
            st.role = "const"
        elif st.is_counter:
            st.role = "counter"
        elif distinct <= 8:
            st.role = "state"
        else:
            st.role = "data"
        stats.append(st)
    return stats
