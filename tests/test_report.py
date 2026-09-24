from __future__ import annotations

import json

from conftest import mk_packet
from ew11_analyzer.analysis import run_analysis
from ew11_analyzer.classify import Marker
from ew11_analyzer.report import packets_to_csv, to_json, to_markdown
from ew11_analyzer.sources.simulator import frame

T0 = 1_000_000.0


def _result():
    pkts = [mk_packet(T0 + i * 0.5, frame(0x40, 0x01, 0x51, [0x00]), seq=i) for i in range(40)]
    pkts.append(mk_packet(T0 + 10.05, frame(0x01, 0x40, 0x11, [0x01, 0x01, 0xFF]), seq=999))
    markers = [Marker(id=1, ts=T0 + 10.0, label="조명켜기")]
    return run_analysis(pkts, markers)


def test_markdown_sections():
    md = to_markdown(_result())
    assert "# AI 분석 요청" in md
    assert "# 수집 개요" in md
    assert "# 이벤트 마커" in md
    assert "# 패밀리 요약" in md
    assert "# 패밀리 상세" in md
    assert "F70A01:10" in md
    assert "이벤트(EVENT)" in md
    assert "xor" in md
    assert "조명켜기" in md


def test_json_parseable():
    d = json.loads(to_json(_result()))
    assert d["total_packets"] == 41
    assert d["families"][0]["verdict"]["verdict"]


def test_csv():
    pkts = [mk_packet(T0 + i, frame(0x40, 0x01, 0x51, [i % 256]), seq=i + 1) for i in range(5)]
    csv_text = packets_to_csv(pkts)
    lines = csv_text.strip().split("\n")
    assert lines[0].startswith("seq,ts,")
    assert len(lines) == 6
    assert "F7 08 40 01 51" in csv_text


def test_markdown_no_markers():
    res = run_analysis([mk_packet(T0 + i, frame(0x40, 0x01, 0x51, [0x00]), seq=i) for i in range(10)], [])
    md = to_markdown(res)
    assert "없음" in md
