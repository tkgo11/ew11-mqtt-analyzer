"""FastAPI surface: REST API + WebSocket live stream + SPA static serving."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .ai import AiConfig
from .config import sanitized_config
from .pipeline import AnalyzerService


class MarkerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="", max_length=200)


class DemoEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str


class AiAnalyzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "anthropic"] | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    model: str | None = Field(default=None, min_length=1, max_length=256)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    save: bool = False


class MqttConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str | None = Field(default=None, min_length=1, max_length=253)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, max_length=4096)
    topic: str | None = Field(default=None, min_length=1, max_length=1024)
    tls: bool | None = None
    client_id: str | None = Field(default=None, min_length=1, max_length=128)


class AnalysisConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefix_len: int | None = Field(default=None, ge=1, le=32)
    event_pre: float | None = Field(default=None, ge=0, le=3600)
    event_post: float | None = Field(default=None, ge=0, le=3600)
    max_packets: int | None = Field(default=None, ge=100, le=10_000_000)
    demo_speed: float | None = Field(default=None, ge=0.05, le=100)


class AiConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "anthropic"] | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    model: str | None = Field(default=None, min_length=1, max_length=256)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)


class ConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mqtt: MqttConfigIn | None = None
    analysis: AnalysisConfigIn | None = None
    ai: AiConfigIn | None = None
    demo: bool | None = None


def resolve_static_dir(explicit: str | None = None) -> Path | None:
    """Locate the built frontend (frontend/dist or a PyInstaller bundle dir)."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("EW11_STATIC_DIR"):
        candidates.append(Path(os.environ["EW11_STATIC_DIR"]))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "static")
    candidates.append(Path(__file__).resolve().parent / "static")  # packaged
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")  # repo dev
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return None


def _packet_routes(app: FastAPI, service: AnalyzerService) -> None:
    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        s = service.status()
        s["demo_events"] = service.demo_event_kinds()
        return s

    @app.get("/api/packets")
    async def packets(
        limit: int = Query(300, ge=1, le=2000),
        before_seq: int | None = Query(default=None, ge=1),
        topic: str | None = None,
    ) -> dict[str, Any]:
        return {"packets": service.recent_packets(limit=limit, before_seq=before_seq, topic=topic)}

    @app.post("/api/packets/clear")
    async def clear_packets() -> dict[str, Any]:
        service.clear_packets()
        return {"ok": True}


def _marker_routes(app: FastAPI, service: AnalyzerService) -> None:
    @app.get("/api/markers")
    async def markers() -> dict[str, Any]:
        return {"markers": [{"id": m.id, "ts": m.ts, "label": m.label} for m in service.markers()]}

    @app.post("/api/markers")
    async def add_marker(body: MarkerIn) -> dict[str, Any]:
        m = service.add_marker(body.label)
        return {"id": m.id, "ts": m.ts, "label": m.label}

    @app.delete("/api/markers/{marker_id}")
    async def delete_marker(marker_id: int) -> dict[str, Any]:
        return {"ok": service.delete_marker(marker_id)}

    @app.post("/api/demo/event")
    async def demo_event(body: DemoEventIn) -> Response:
        try:
            n = await service.inject_demo_event(body.kind)
        except RuntimeError:
            return JSONResponse({"error": "데모 모드가 아닙니다"}, status_code=400)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"ok": True, "sent": n})


def _analysis_routes(app: FastAPI, service: AnalyzerService) -> None:
    @app.get("/api/analysis")
    async def analysis(
        prefix_len: int | None = Query(default=None, ge=1, le=32),
        event_pre: float | None = Query(default=None, ge=0, le=3600),
        event_post: float | None = Query(default=None, ge=0, le=3600),
    ) -> dict[str, Any]:
        result = await asyncio.to_thread(service.analyze, prefix_len, event_pre, event_post)
        return result.to_dict()

    @app.get("/api/report")
    async def report(format: str = Query("md", pattern="^(md|json)$")) -> Response:
        text = await asyncio.to_thread(service.report, format)
        if format == "json":
            return JSONResponse(content=json.loads(text))
        fname = f"ew11-report-{int(time.time())}.md"
        return PlainTextResponse(
            text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    @app.get("/api/export.csv")
    async def export_csv() -> Response:
        csv_text = await asyncio.to_thread(service.export_csv)
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="ew11-packets-{int(time.time())}.csv"'},
        )

    @app.post("/api/ai/analyze")
    async def ai_analyze(body: AiAnalyzeIn | None = None) -> Response:
        body = body or AiAnalyzeIn()
        cfg = service.cfg.ai
        override = AiConfig(
            provider=body.provider or cfg.provider,
            base_url=body.base_url or cfg.base_url,
            api_key=body.api_key if body.api_key is not None else cfg.api_key,
            model=body.model or cfg.model,
            max_tokens=body.max_tokens or cfg.max_tokens,
        )
        if body.save:
            service.cfg.ai = override
            service.update_config(service.cfg)
        try:
            text = await service.ai_analyze(override)
        except Exception as e:
            return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)
        return JSONResponse({"ok": True, "text": text})


def _config_routes(app: FastAPI, service: AnalyzerService) -> None:
    @app.get("/api/config")
    async def get_config() -> dict[str, Any]:
        return sanitized_config(service.cfg)

    @app.put("/api/config")
    async def put_config(body: ConfigIn) -> dict[str, Any]:
        cfg = service.cfg
        for section_name, section in (("mqtt", cfg.mqtt), ("analysis", cfg.analysis), ("ai", cfg.ai)):
            values = getattr(body, section_name)
            if values is not None:
                for k, v in values.model_dump(exclude_none=True).items():
                    setattr(section, k, v)
        if body.demo is not None:
            cfg.demo = body.demo
        service.update_config(cfg)
        return {"ok": True, "config": sanitized_config(cfg)}

    @app.post("/api/source/reconnect")
    async def reconnect() -> dict[str, Any]:
        await service.reconnect()
        return {"ok": True}


def _ws_route(app: FastAPI, service: AnalyzerService) -> None:
    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        q = service.subscribe()
        try:
            await websocket.send_json({"type": "status", "data": {"status": service.status()["status"]}})
            while True:
                obj = await q.get()
                await websocket.send_json(obj)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            service.unsubscribe(q)


def create_app(
    service: AnalyzerService, static_dir: str | None = None, manage_lifecycle: bool = False
) -> FastAPI:
    kwargs: dict[str, Any] = {}
    if manage_lifecycle:

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            await service.start()
            yield
            await service.stop()

        kwargs["lifespan"] = lifespan
    app = FastAPI(title="EW11 MQTT Packet Analyzer", version="0.1.0", **kwargs)
    _packet_routes(app, service)
    _marker_routes(app, service)
    _analysis_routes(app, service)
    _config_routes(app, service)
    _ws_route(app, service)

    static = resolve_static_dir(static_dir)
    if static:
        app.mount("/", StaticFiles(directory=str(static), html=True), name="spa")
    else:

        @app.get("/")
        async def root() -> HTMLResponse:
            return HTMLResponse(
                "<h1>EW11 MQTT Packet Analyzer</h1><p>Frontend not built. "
                "Run <code>cd frontend && npm run build</code>, or set EW11_STATIC_DIR. "
                "API is under <code>/api</code>.</p>"
            )

    return app
