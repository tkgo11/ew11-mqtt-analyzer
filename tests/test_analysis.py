from __future__ import annotations

from conftest import mk_packet
from ew11_analyzer.analysis import run_analysis
from ew11_analyzer.classify import Marker
from ew11_analyzer.sources.simulator import frame

T0 = 1_000_000.0


def _mixed_traffic() -> list:
    pkts = []
    seq = 0
    # periodic poll every 0.5s for 60s
    for i in range(120):
        pkts.append(mk_packet(T0 + i * 0.5, frame(0x40, 0x01, 0x51, [0x00]), seq=seq))
        seq += 1
    # slower status broadcast every 2s
    for i in range(30):
        pkts.append(mk_packet(T0 + i * 2.0, frame(0x40, 0x01, 0x11, [0x01, 0x00, i % 256, 0x00]), seq=seq))
        seq += 1
    return pkts


def test_run_analysis_structure():
    pkts = _mixed_traffic()
    markers = [Marker(id=1, ts=T0 + 10.0, label="조명")]
    pkts.append(mk_packet(T0 + 10.05, frame(0x01, 0x40, 0x11, [0x01, 0x01, 0xFF]), seq=9999))
    result = run_analysis(pkts, markers)
    d = result.to_dict()
    assert d["total_packets"] == len(pkts)
    assert d["families"]
    sigs = {f["sig"] for f in d["families"]}
    assert "F70A01:10" in sigs  # the command family separated at prefix 3
    evt = next(f for f in d["families"] if f["sig"] == "F70A01:10")
    assert evt["verdict"]["verdict"] == "EVENT"
    idle = next(f for f in d["families"] if f["sig"].startswith("F70840"))
    assert idle["verdict"]["verdict"] == "IDLE"
    assert idle["checksum"]["algo"] == "xor"
    assert idle["bytemap"]
    assert d["diffs"]


def test_notes_without_markers():
    result = run_analysis(_mixed_traffic()[:30], [])
    assert any("마커" in n for n in result.notes)


def test_empty_input():
    result = run_analysis([], [])
    assert result.total_packets == 0
    assert result.families == []


def test_max_families_cap():
    pkts = [mk_packet(T0 + i, bytes([0xF7, i % 200 + 1, i % 256, 0xAA, 0xEE]), seq=i) for i in range(300)]
    result = run_analysis(pkts, [], max_families=5)
    assert len(result.families) <= 5
    assert result.total_families > 5
