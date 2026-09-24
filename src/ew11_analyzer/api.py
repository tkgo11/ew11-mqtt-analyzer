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
from typing import Any

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai import AiConfig
from .config import sanitized_config
from .pipeline import AnalyzerService


class MarkerIn(BaseModel):
    label: str = ""


class DemoEventIn(BaseModel):
    kind: str


class AiAnalyzeIn(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    save: bool = False


class ConfigIn(BaseModel):
    mqtt: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    ai: dict[str, Any] | None = None
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
        limit: int = Query(300, le=2000),
        before_seq: int | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        return {"packets": service.recent_packets(limit=limit, before_seq=before_seq, topic=topic)}

    @app.post("/api/packets/clear")
    async def clear_packets() -> dict[str, Any]:
        service.storage.clear_packets()
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
        prefix_len: int | None = None,
        event_pre: float | None = None,
        event_post: float | None = None,
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
    async def ai_analyze(body: AiAnalyzeIn) -> Response:
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
            if values:
                for k, v in values.items():
                    if hasattr(section, k):
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
