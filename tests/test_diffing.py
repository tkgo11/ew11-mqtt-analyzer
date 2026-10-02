from __future__ import annotations

from conftest import mk_packet
from ew11_analyzer.classify import Marker
from ew11_analyzer.diffing import diff_around_markers
from ew11_analyzer.sources.simulator import frame

T0 = 1_000_000.0


def _baseline(n: int = 20) -> list:
    """Periodic lobby poll every 0.5s."""
    return [mk_packet(T0 + i * 0.5, frame(0x40, 0x01, 0x51, [0x00]), seq=i) for i in range(n)]


def test_novel_family_detected():
    pkts = _baseline()
    marker = Marker(id=1, ts=T0 + 4.0, label="light")
    cmd = frame(0x01, 0x40, 0x11, [0x01, 0x01, 0xFF])
    pkts.append(mk_packet(marker.ts + 0.05, cmd, seq=999))
    diffs = diff_around_markers(pkts, [marker])
    assert len(diffs) == 1
    novel = [h for h in diffs[0].hits if h.novel]
    assert len(novel) == 1
    assert novel[0].count_in == 1
    assert novel[0].samples_in == [cmd.hex(" ").upper()]


def test_changed_positions_detected():
    # status family broadcasts value 0; during event window the state byte flips
    base = [mk_packet(T0 + i, frame(0x40, 0x01, 0x11, [0x00, 0x00, 0x00, 0x00]), seq=i) for i in range(30)]
    marker = Marker(id=1, ts=T0 + 15.0, label="light")
    evt = mk_packet(marker.ts + 0.1, frame(0x40, 0x01, 0x11, [0x01, 0x00, 0x00, 0x00]), seq=999)
    diffs = diff_around_markers([*base, evt], [marker])
    hit = next(h for h in diffs[0].hits if not h.novel)
    # data byte index 5 changed (F7 LEN DST SRC CMD d0...)
    assert 5 in hit.changed_positions


def test_marker_outside_window_excluded():
    pkts = _baseline()
    marker = Marker(id=1, ts=T0 + 100.0, label="late")  # beyond all packets
    diffs = diff_around_markers(pkts, [marker])
    assert diffs[0].hits == []


def test_multiple_markers():
    pkts = _baseline()
    ms = [Marker(id=1, ts=T0 + 2.0, label="a"), Marker(id=2, ts=T0 + 6.0, label="b")]
    diffs = diff_around_markers(pkts, ms)
    assert len(diffs) == 2
    assert all(d.hits for d in diffs)  # baseline polls inside both windows


def test_late_baseline_values_are_not_reported_as_event_changes():
    packets = [mk_packet(T0 + i, b"\xf7\x04\x40\x00", seq=i) for i in range(64)]
    packets.append(mk_packet(T0 + 64, b"\xf7\x04\x40\x01", seq=64))
    packets.append(mk_packet(T0 + 100.1, b"\xf7\x04\x40\x01", seq=65))
    marker = Marker(id=1, ts=T0 + 100, label="event")
    for ordered in [packets, list(reversed(packets))]:
        hit = diff_around_markers(ordered, [marker])[0].hits[0]
        assert hit.changed_positions == []
        assert not hit.novel
        assert len(hit.samples_out) == 4


def test_late_event_changes_are_detected_beyond_preview_samples():
    packets = [mk_packet(T0, b"\xf7\x04\x40\x00")]
    packets.extend(
        mk_packet(T0 + 100 + i * 0.01, b"\xf7\x04\x40\x00", seq=i + 1) for i in range(64)
    )
    packets.append(mk_packet(T0 + 101, b"\xf7\x04\x40\x01", seq=65))
    marker = Marker(id=1, ts=T0 + 100, label="event")
    for ordered in [packets, list(reversed(packets))]:
        hit = diff_around_markers(ordered, [marker])[0].hits[0]
        assert hit.changed_positions == [3]
        assert hit.count_in == 65
        assert len(hit.samples_in) == 6
        assert hit.samples_in[0] == "F7 04 40 01"
        assert hit.sample_changes == [[3], [], [], [], [], []]


def test_preview_covers_each_changed_position():
    packets = [mk_packet(T0, b"\xf7\x05\x40\x00\x00")]
    packets.extend(mk_packet(T0 + 100 + i * 0.01, b"\xf7\x05\x40\x00\x00", seq=i + 1) for i in range(10))
    packets.append(mk_packet(T0 + 100.5, b"\xf7\x05\x40\x00\x01", seq=20))
    packets.append(mk_packet(T0 + 100.6, b"\xf7\x05\x40\x01\x00", seq=21))
    packets.append(mk_packet(T0 + 100.7, b"\xf7\x05\x40\x01\x01", seq=22))
    hit = diff_around_markers(packets, [Marker(id=1, ts=T0 + 100, label="event")])[0].hits[0]
    assert hit.changed_positions == [3, 4]
    assert hit.samples_in[0] == "F7 05 40 01 01"
    assert hit.sample_changes[:2] == [[3, 4], []]
    assert len(hit.samples_in) == len(hit.sample_changes) == 6
