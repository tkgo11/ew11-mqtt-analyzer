"""Packet family signatures and grouping.

Packets are grouped into "families" by a signature derived from their leading
bytes (usually STX + length or STX + device address) plus the total length.
Families are the unit of analysis: periodicity, byte variance, checksum
detection and event correlation are all computed per family.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .packets import Packet

DEFAULT_PREFIX_LEN = 2


def signature(payload: bytes, prefix_len: int = DEFAULT_PREFIX_LEN) -> str:
    """Return a family signature like ``'F70D:13'`` (prefix-hex + total length)."""
    head = payload[:prefix_len].hex().upper() if payload else ""
    return f"{head}:{len(payload)}"


def signature_head(sig: str) -> str:
    """Return the hex-prefix part of a signature for display."""
    return sig.split(":", 1)[0]


def group_families(
    packets: Iterable[Packet], prefix_len: int = DEFAULT_PREFIX_LEN
) -> dict[str, list[Packet]]:
    fams: dict[str, list[Packet]] = defaultdict(list)
    for p in packets:
        fams[signature(p.payload, prefix_len)].append(p)
    return dict(fams)
