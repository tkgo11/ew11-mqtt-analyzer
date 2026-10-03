from __future__ import annotations

import pytest

from ew11_analyzer.classify import Marker, classify_family

T0 = 1_000_000.0


def periodic_ts(n: int = 40, interval: float = 1.0, start: float = T0) -> list[float]:
    return [start + i * interval for i in range(n)]


def test_periodic_is_idle_no_markers():
    v = classify_family("F708:8", periodic_ts(), ["t"], markers=[], start=T0, end=T0 + 60)
    assert v.verdict == "IDLE"
    assert v.periodicity > 0.9


def test_event_only_family_is_event():
    # 3 packets, all right after markers, none in baseline
    markers = [
        Marker(id=1, ts=T0 + 10.0, label="on"),
        Marker(id=2, ts=T0 + 30.0, label="on"),
        Marker(id=3, ts=T0 + 50.0, label="on"),
    ]
    ts = [T0 + 10.1, T0 + 30.15, T0 + 50.05]
    v = classify_family("F70A01:10", ts, ["t"], markers=markers, start=T0, end=T0 + 60)
    assert v.verdict == "EVENT"
    assert v.event_lift == 99.0
    assert v.marker_ids == [1, 2, 3]


def test_single_packet_in_window_is_event_weak():
    markers = [Marker(id=1, ts=T0 + 10.0, label="x")]
    v = classify_family("X:4", [T0 + 10.2], ["t"], markers=markers, start=T0, end=T0 + 60)
    assert v.verdict == "EVENT"
    assert v.confidence < 0.6


def test_single_packet_no_window_is_unknown():
    v = classify_family("X:4", [T0 + 10.2], ["t"], markers=[], start=T0, end=T0 + 60)
    assert v.verdict == "UNKNOWN"


def test_periodic_stays_idle_despite_window_overlap():
    # dense periodic traffic; marker windows cover ~half the capture
    markers = [Marker(id=i, ts=T0 + 5 + i * 10, label="m") for i in range(5)]
    v = classify_family("F708:8", periodic_ts(120, 0.5), ["t"], markers=markers, start=T0, end=T0 + 60)
    assert v.verdict == "IDLE"
    assert v.event_lift is not None and v.event_lift < 2.0


def test_irregular_no_markers_is_unknown():
    ts = [T0 + 1.0, T0 + 1.2, T0 + 7.7, T0 + 8.0, T0 + 30.0]
    v = classify_family("Y:5", ts, ["t"], markers=[], start=T0, end=T0 + 60)
    assert v.verdict == "UNKNOWN"


def test_burst_family_mixed_or_event():
    # irregular bursts both inside and outside windows -> not clean event
    markers = [Marker(id=1, ts=T0 + 10.0, label="m")]
    ts = [T0 + 10.1, T0 + 10.3, T0 + 22.0, T0 + 22.4, T0 + 22.8, T0 + 45.0]
    v = classify_family("Z:6", ts, ["t"], markers=markers, start=T0, end=T0 + 60)
    assert v.verdict in {"MIXED", "IDLE", "EVENT"}


@pytest.mark.parametrize("offset", [0, 10])
def test_event_lift_clips_windows_to_capture(offset):
    markers = [
        Marker(id=1, ts=T0 + offset, label="edge"),
        Marker(id=2, ts=T0 - 100, label="old"),
        Marker(id=3, ts=T0 + 100, label="future"),
    ]
    v = classify_family(
        "X:4", [T0 + t for t in [1, 3, 5, 9]], ["t"],
        markers=markers, start=T0, end=T0 + 10, pre=2, post=2,
    )
    assert v.event_count == 1
    assert v.baseline_count == 3
    assert v.event_lift == pytest.approx((1 / 2) / (3 / 8))
    assert v.marker_ids == [1]


def test_overlapping_windows_count_exposure_and_packets_once():
    markers = [Marker(id=1, ts=T0 + 2, label="a"), Marker(id=2, ts=T0 + 4, label="b")]
    v = classify_family(
        "X:4", [T0 + i + 0.5 for i in range(10)], ["t"],
        markers=markers, start=T0, end=T0 + 10, pre=2, post=2,
    )
    assert v.event_count == 6
    assert v.baseline_count == 4
    assert v.event_lift == pytest.approx(1)


@pytest.mark.parametrize("offsets", [[0.5], [0, 0.5, 1]])
def test_no_baseline_exposure_is_unknown(offsets):
    v = classify_family(
        "X:4", [T0 + t for t in offsets], ["t"],
        markers=[Marker(id=1, ts=T0, label="all")], start=T0, end=T0 + 1,
    )
    assert v.event_count == len(offsets)
    assert v.baseline_count == 0
    assert v.event_lift is None
    assert v.verdict == "UNKNOWN"


def test_zero_width_event_window_cannot_establish_lift():
    v = classify_family(
        "X:4", [T0 + 1], ["t"],
        markers=[Marker(id=1, ts=T0 + 1, label="point")],
        start=T0, end=T0 + 2, pre=0, post=0,
    )
    assert v.event_count == 1
    assert v.event_lift is None
    assert v.verdict == "UNKNOWN"


def test_zero_duration_capture_does_not_invent_a_rate():
    v = classify_family(
        "X:4", [T0], ["t"], markers=[Marker(id=1, ts=T0, label="point")], start=T0, end=T0,
    )
    assert v.rate_per_min == 0
    assert v.event_lift is None
    assert v.verdict == "UNKNOWN"
