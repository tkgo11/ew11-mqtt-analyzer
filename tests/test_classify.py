from __future__ import annotations

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
