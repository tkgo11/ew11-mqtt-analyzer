"""Packet model and MQTT payload normalization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_SEPARATORS = re.compile(r"0x|\s|,|:|;|-")

MAX_RAW_PREVIEW = 512


@dataclass
class RawMessage:
    """A message as received from a source (MQTT broker or simulator)."""

    ts: float
    topic: str
    payload: bytes


@dataclass
class Packet:
    """A normalized packet ready for analysis."""

    seq: int
    ts: float
    topic: str
    payload: bytes
    fmt: str  # 'hex' | 'json' | 'raw'
    raw: str

    @property
    def hex(self) -> str:
        return self.payload.hex(" ").upper()

    @property
    def size(self) -> int:
        return len(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "topic": self.topic,
            "hex": self.hex,
            "len": self.size,
            "fmt": self.fmt,
            "raw": self.raw,
        }


def _preview(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    return text[:MAX_RAW_PREVIEW]


def _try_json_extract(obj: object) -> bytes | None:
    """Extract packet bytes from a decoded JSON object, if a known field exists."""
    if not isinstance(obj, dict):
        return None
    for key in ("payload", "data", "hex", "packet", "raw", "value"):
        if key not in obj:
            continue
        v = obj[key]
        if isinstance(v, str):
            payload, fmt, _ = normalize_payload(v.encode("utf-8"))
            if fmt == "hex":
                return payload
            return v.encode("utf-8")
        if isinstance(v, list) and v and all(isinstance(x, int) and 0 <= x <= 255 for x in v):
            return bytes(v)
    return None


def normalize_payload(data: bytes) -> tuple[bytes, str, str]:
    """Normalize an MQTT payload to packet bytes.

    Returns ``(payload, fmt, raw_preview)`` where fmt is one of:

    - ``'hex'``: payload was a hex string (most EW11 bridges publish hex)
    - ``'json'``: JSON wrapper carrying a payload/data field
    - ``'raw'``: anything else, used as-is
    """
    raw = _preview(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, "raw", raw

    stripped = text.strip()
    if not stripped:
        return data, "raw", raw

    if stripped[0] in "{[":
        try:
            obj = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            obj = None
        if obj is not None:
            extracted = _try_json_extract(obj)
            if extracted is not None:
                return extracted, "json", raw
            return data, "json", raw

    cleaned = _SEPARATORS.sub("", stripped)
    if len(cleaned) >= 4 and len(cleaned) % 2 == 0 and all(c in _HEX_CHARS for c in cleaned):
        try:
            return bytes.fromhex(cleaned), "hex", raw
        except ValueError:
            pass

    return data, "raw", raw
