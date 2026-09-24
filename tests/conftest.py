from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ew11_analyzer.packets import Packet
from ew11_analyzer.sources.simulator import frame


def mk_packet(ts: float, payload: bytes, topic: str = "ew11/recv", seq: int = 0) -> Packet:
    return Packet(seq=seq, ts=ts, topic=topic, payload=payload, fmt="hex", raw=payload.hex())


def hex_packets(
    start_ts: float, interval: float, payloads: list[bytes], topic: str = "ew11/recv"
) -> list[Packet]:
    """Packets cycling through payloads at a fixed interval starting at start_ts."""
    return [
        mk_packet(start_ts + i * interval, payloads[i % len(payloads)], topic, seq=i)
        for i in range(len(payloads))
    ]


@pytest.fixture()
def sim_frame():
    return frame
