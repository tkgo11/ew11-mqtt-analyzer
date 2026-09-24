"""Checksum algorithm detection for packet families.

Korean wallpad / RS485 protocols almost always terminate frames with a
checksum. This module brute-forces the common candidates:

- XOR of covered bytes
- 8-bit sum (and inverted variant)
- CRC-8 (SMBus poly 0x07, MAXIM/Dallas poly 0x31 reflected)
- CRC-16 (MODBUS, IBM, CCITT — both wire byte orders)

It also probes plausible covered ranges (from byte 0..3 up to the checksum
position) and allows a constant trailing byte (ETX like 0xEE / 0x03 / CR)
after the checksum.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import reduce
from operator import xor
from typing import Any


@dataclass
class ChecksumMatch:
    algo: str  # detector name, e.g. 'xor', 'sum8', 'crc16-modbus'
    pos: int  # index of the first checksum byte in the packet
    size: int  # checksum width in bytes (1 or 2)
    covered_start: int  # first byte index covered by the checksum
    covered_end: int  # one past the last covered byte (== pos)
    rate: float  # fraction of samples that validate
    verified: bool  # rate == 1.0 on all probed samples
    endian: str  # 'big' | 'little' | '' for 1-byte checksums

    def to_dict(self) -> dict[str, Any]:
        return {
            "algo": self.algo,
            "pos": self.pos,
            "size": self.size,
            "covered": [self.covered_start, self.covered_end],
            "rate": round(self.rate, 4),
            "verified": self.verified,
            "endian": self.endian,
        }


def _xor8(data: bytes) -> int:
    return reduce(xor, data, 0)


def _sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def _sum8_inv(data: bytes) -> int:
    return (~sum(data)) & 0xFF


def _crc16_reflected(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _crc16_msb(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def _crc8_msb(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc & 0xFF


def _crc8_reflected(data: bytes, poly: int, init: int) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
    return crc & 0xFF


_D1: list[tuple[str, Callable[[bytes], int]]] = [
    ("xor", _xor8),
    ("sum8", _sum8),
    ("sum8-inv", _sum8_inv),
    ("crc8", lambda d: _crc8_msb(d, 0x07, 0x00)),
    ("crc8-maxim", lambda d: _crc8_reflected(d, 0x8C, 0x00)),
]

_D2: list[tuple[str, Callable[[bytes], int]]] = [
    ("crc16-modbus", lambda d: _crc16_reflected(d, 0xA001, 0xFFFF)),
    ("crc16-ibm", lambda d: _crc16_reflected(d, 0xA001, 0x0000)),
    ("crc16-ccitt", lambda d: _crc16_msb(d, 0x1021, 0xFFFF)),
    ("crc16-ccitt0", lambda d: _crc16_msb(d, 0x1021, 0x0000)),
    ("sum16", lambda d: sum(d) & 0xFFFF),
]

MATCH_THRESHOLD = 0.95


def _matches(
    samples: list[bytes], fn: Callable[[bytes], int], start: int, pos: int, size: int
) -> tuple[int, str]:
    """Count matching samples; for 2-byte checksums try both wire orders."""
    hits_be = hits_le = 0
    for s in samples:
        v = fn(s[start:pos])
        trailer = s[pos : pos + size]
        if size == 1:
            hits_be += int(v == trailer[0])
        else:
            hits_be += int(v == int.from_bytes(trailer, "big"))
            hits_le += int(v == int.from_bytes(trailer, "little"))
    if size == 1 or hits_be >= hits_le:
        return hits_be, "big"
    return hits_le, "little"


def detect_checksum(samples: list[bytes], max_samples: int = 96) -> list[ChecksumMatch]:
    """Return plausible checksum matches (rate >= 0.95), best first."""
    if len(samples) < 3:
        return []
    samples = samples[:max_samples]
    n = len(samples[0])
    if n < 4 or any(len(s) != n for s in samples):
        return []

    matches: list[ChecksumMatch] = []
    for size in (1, 2):
        for tail in (0, 1):
            pos = n - size - tail
            if pos < 2:
                continue
            # a trailing byte after the checksum must be constant (ETX)
            if tail == 1 and len({s[-1] for s in samples}) != 1:
                continue
            dets = _D1 if size == 1 else _D2
            for start in range(min(pos, 3) + 1):
                for name, fn in dets:
                    hits, endian = _matches(samples, fn, start, pos, size)
                    rate = hits / len(samples)
                    if rate >= MATCH_THRESHOLD:
                        matches.append(
                            ChecksumMatch(
                                algo=name,
                                pos=pos,
                                size=size,
                                covered_start=start,
                                covered_end=pos,
                                rate=rate,
                                verified=rate >= 0.999,
                                endian="" if size == 1 else endian,
                            )
                        )
    # best first; on ties prefer wider coverage (smaller start) then earlier pos
    matches.sort(key=lambda m: (-m.rate, m.covered_start, m.pos))
    return matches[:5]
