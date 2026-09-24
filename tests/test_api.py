from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from ew11_analyzer.api import create_app
from ew11_analyzer.config import AppConfig
from ew11_analyzer.packets import RawMessage
from ew11_analyzer.pipeline import AnalyzerService


@pytest.fixture()
def svc(tmp_path):
    cfg = AppConfig(demo=False)
    service = AnalyzerService(cfg, tmp_path)
    yield service
    service.storage.close()


@pytest.fixture()
def client(svc):
    return TestClient(create_app(svc))


def _ingest(svc, payload: bytes, ts: float | None = None, topic: str = "ew11/recv"):
    svc.ingest(RawMessage(ts=ts or time.time(), topic=topic, payload=payload))


def test_status(client, svc):
    r = client.get("/api/status")
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "live"
    assert d["total_packets"] == 0


def test_ingest_and_query(client, svc):
    _ingest(svc, b"F7 08 40 01 51 00 18 EE")
    _ingest(svc, b"AA BB CC DD")
    svc.storage.flush()
    r = client.get("/api/packets?limit=10")
    pkts = r.json()["packets"]
    assert len(pkts) == 2
    assert pkts[0]["seq"] > pkts[1]["seq"]  # newest first
    assert pkts[0]["hex"] == "AA BB CC DD"


def test_markers_crud(client, svc):
    r = client.post("/api/markers", json={"label": "거실 조명"})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert client.get("/api/markers").json()["markers"][0]["label"] == "거실 조명"
    assert client.delete(f"/api/markers/{mid}").json()["ok"]
    assert client.get("/api/markers").json()["markers"] == []


def test_analysis_endpoint(client, svc):
    for i in range(30):
        _ingest(svc, b"F7 08 40 01 51 00 18 EE", ts=1000.0 + i * 0.5)
    svc.storage.flush()
    r = client.get("/api/analysis")
    assert r.status_code == 200
    d = r.json()
    assert d["total_packets"] == 30
    fams = {f["sig"]: f for f in d["families"]}
    assert "F70840:8" in fams
    assert fams["F70840:8"]["verdict"]["verdict"] == "IDLE"
    assert fams["F70840:8"]["checksum"]["algo"] == "xor"


def test_report_md_and_json(client, svc):
    for i in range(10):
        _ingest(svc, b"F7 08 40 01 51 00 18 EE", ts=1000.0 + i)
    r = client.get("/api/report?format=md")
    assert r.status_code == 200
    assert "# AI 분석 요청" in r.text
    r2 = client.get("/api/report?format=json")
    assert r2.json()["total_packets"] == 10


def test_export_csv(client, svc):
    _ingest(svc, b"F7 08 40 01 51 00 18 EE")
    r = client.get("/api/export.csv")
    assert r.status_code == 200
    assert "F7 08 40 01 51 00 18 EE" in r.text


def test_config_roundtrip(client):
    r = client.get("/api/config")
    assert r.json()["mqtt"]["port"] == 1883
    r2 = client.put(
        "/api/config",
        json={"mqtt": {"host": "192.168.0.10", "port": 2883}, "analysis": {"prefix_len": 4}},
    )
    assert r2.json()["config"]["mqtt"]["host"] == "192.168.0.10"


def test_demo_event_requires_demo_mode(client):
    r = client.post("/api/demo/event", json={"kind": "light_on"})
    assert r.status_code == 400


def test_ai_analyze_no_key(client):
    r = client.post("/api/ai/analyze", json={})
    assert r.status_code == 502


def test_websocket_receives_packets(svc):
    with TestClient(create_app(svc)) as c, c.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "status"
        _ingest(svc, b"F7 08 40 01 51 00 18 EE")
        msg = ws.receive_json()
        assert msg["type"] == "packet"
        assert msg["data"]["hex"] == "F7 08 40 01 51 00 18 EE"


def test_demo_mode_full_flow(tmp_path):
    cfg = AppConfig(demo=True)
    cfg.analysis.demo_speed = 0.15
    svc = AnalyzerService(cfg, tmp_path)
    with TestClient(create_app(svc, manage_lifecycle=True)) as c:
        st = c.get("/api/status").json()
        assert st["mode"] == "demo"
        assert st["demo_events"]
        time.sleep(1.0)
        for _ in range(3):
            c.post("/api/markers", json={"label": "조명"})
            c.post("/api/demo/event", json={"kind": "light_on"})
            time.sleep(0.4)
        time.sleep(0.3)
        d = c.get("/api/analysis").json()
        by_sig = {f["sig"]: f for f in d["families"]}
        assert by_sig["F70A01:10"]["verdict"]["verdict"] == "EVENT"
        idle_sigs = [s for s, f in by_sig.items() if f["verdict"]["verdict"] == "IDLE"]
        assert len(idle_sigs) >= 4
        md = c.get("/api/report?format=md").text
        assert "이벤트(EVENT)" in md
