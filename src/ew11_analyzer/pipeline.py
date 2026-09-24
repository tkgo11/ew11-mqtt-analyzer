"""Ingest pipeline and service façade.

Owns the packet source (MQTT or simulator), normalizes payloads, persists to
SQLite, tracks live stats, and fans packets out to WebSocket subscribers.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from pathlib import Path
from typing import Any

from .ai import AiConfig, analyze_report
from .analysis import AnalysisResult, run_analysis
from .classify import Marker
from .config import AppConfig, save_config
from .packets import Packet, RawMessage, normalize_payload
from .report import packets_to_csv, to_json, to_markdown
from .sources.base import PacketSource
from .sources.mqtt import MqttSource
from .sources.simulator import EVENT_KINDS, SimulatedWallpad
from .storage import Storage

FLUSH_INTERVAL = 0.4
RATE_WINDOW_S = 15.0


class AnalyzerService:
    def __init__(self, cfg: AppConfig, data_dir: Path):
        self.cfg = cfg
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(self.data_dir / "packets.db", max_packets=cfg.analysis.max_packets)
        self._seq = self.storage.max_seq()
        self._source: PacketSource | None = None
        self._status = "init"
        self._started_at = 0.0
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._rx_ts: deque[float] = deque(maxlen=10_000)
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        self._started_at = time.time()
        await self._start_source()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
        await self._stop_source()
        self.storage.close()

    async def _start_source(self) -> None:
        if self.cfg.demo:
            src: PacketSource = SimulatedWallpad(speed=self.cfg.analysis.demo_speed)
        else:
            src = MqttSource(self.cfg.mqtt)
        self._source = src
        self._set_status("connecting")
        await src.start(self.ingest, self._set_status)

    async def _stop_source(self) -> None:
        if self._source is not None:
            await self._source.stop()
            self._source = None

    async def reconnect(self) -> None:
        async with self._lock:
            await self._stop_source()
            await self._start_source()

    # ---------------------------------------------------------------- ingest
    def ingest(self, raw: RawMessage) -> None:
        payload, fmt, preview = normalize_payload(raw.payload)
        self._seq += 1
        pkt = Packet(seq=self._seq, ts=raw.ts, topic=raw.topic, payload=payload, fmt=fmt, raw=preview)
        self.storage.add_packet(pkt)
        self._rx_ts.append(raw.ts)
        self._broadcast({"type": "packet", "data": pkt.to_dict()})

    async def _flush_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(FLUSH_INTERVAL)
                self.storage.flush()
        except asyncio.CancelledError:
            pass

    # --------------------------------------------------------------- pub/sub
    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(q)

    def _broadcast(self, obj: dict[str, Any]) -> None:
        for q in self._subs:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(obj)

    def _set_status(self, s: str) -> None:
        self._status = s
        self._broadcast({"type": "status", "data": {"status": s}})

    # ----------------------------------------------------------------- views
    def status(self) -> dict[str, Any]:
        now = time.time()
        recent = sum(1 for t in self._rx_ts if now - t <= RATE_WINDOW_S)
        return {
            "mode": "demo" if self.cfg.demo else "live",
            "source": self._source.name if self._source else None,
            "status": self._status,
            "broker": f"{self.cfg.mqtt.host}:{self.cfg.mqtt.port}",
            "topic": self.cfg.mqtt.topic,
            "uptime_s": round(now - self._started_at, 1) if self._started_at else 0,
            "total_packets": self.storage.count(),
            "rate_per_s": round(recent / RATE_WINDOW_S, 2),
            "markers": len(self.storage.markers()),
            "topics": self.storage.topics(),
        }

    def recent_packets(
        self, limit: int = 300, before_seq: int | None = None, topic: str | None = None
    ) -> list[dict[str, Any]]:
        pkts = self.storage.query(limit=limit, before_seq=before_seq, topic=topic, newest_first=True)
        return [p.to_dict() for p in pkts]

    # --------------------------------------------------------------- markers
    def add_marker(self, label: str) -> Marker:
        m = self.storage.add_marker(time.time(), label)
        self._broadcast({"type": "marker", "data": {"id": m.id, "ts": m.ts, "label": m.label}})
        return m

    def markers(self) -> list[Marker]:
        return self.storage.markers()

    def delete_marker(self, marker_id: int) -> bool:
        return self.storage.delete_marker(marker_id)

    # -------------------------------------------------------------- analysis
    def analyze(
        self, prefix_len: int | None = None, pre: float | None = None, post: float | None = None
    ) -> AnalysisResult:
        ac = self.cfg.analysis
        self.storage.flush()
        packets = self.storage.query()
        markers = self.storage.markers()
        return run_analysis(
            packets,
            markers,
            prefix_len=prefix_len or ac.prefix_len,
            pre=ac.event_pre if pre is None else pre,
            post=ac.event_post if post is None else post,
        )

    def report(self, fmt: str = "md") -> str:
        result = self.analyze()
        if fmt == "json":
            return to_json(result)
        return to_markdown(result)

    def export_csv(self) -> str:
        self.storage.flush()
        return packets_to_csv(self.storage.query())

    async def ai_analyze(self, cfg: AiConfig | None = None) -> str:
        return await analyze_report(self.report("md"), cfg or self.cfg.ai)

    # ----------------------------------------------------------------- misc
    def demo_event_kinds(self) -> dict[str, str] | None:
        return EVENT_KINDS if isinstance(self._source, SimulatedWallpad) else None

    async def inject_demo_event(self, kind: str) -> int:
        if not isinstance(self._source, SimulatedWallpad):
            raise RuntimeError("not in demo mode")
        return await self._source.inject_event(kind)

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        save_config(self.data_dir, cfg)
