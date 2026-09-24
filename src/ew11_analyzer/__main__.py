"""CLI entrypoint: ``python -m ew11_analyzer``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from .api import create_app
from .config import load_config
from .pipeline import AnalyzerService


def build_service(args: argparse.Namespace) -> tuple[AnalyzerService, FastAPI]:
    data_dir = Path(args.data_dir).resolve()
    cfg = load_config(data_dir)
    if args.demo:
        cfg.demo = True
    if args.mqtt_host:
        cfg.mqtt.host = args.mqtt_host
    if args.mqtt_port:
        cfg.mqtt.port = args.mqtt_port
    if args.topic:
        cfg.mqtt.topic = args.topic
    if args.demo_speed:
        cfg.analysis.demo_speed = args.demo_speed

    service = AnalyzerService(cfg, data_dir)
    app = create_app(service, static_dir=args.static_dir, manage_lifecycle=True)
    return service, app


def main() -> int:
    p = argparse.ArgumentParser(
        prog="ew11-analyzer",
        description="EW11 MQTT packet auto-analysis for wallpad RS485 traffic",
    )
    p.add_argument("--host", default="0.0.0.0", help="listen host (default 0.0.0.0)")
    p.add_argument("--port", type=int, default=8000, help="listen port (default 8000)")
    p.add_argument("--data-dir", default="data", help="data directory (default ./data)")
    p.add_argument("--static-dir", default=None, help="frontend dist directory")
    p.add_argument("--demo", action="store_true", help="run with the built-in wallpad simulator")
    p.add_argument("--demo-speed", type=float, default=None, help="simulator speed multiplier")
    p.add_argument("--mqtt-host", default=None)
    p.add_argument("--mqtt-port", type=int, default=None)
    p.add_argument("--topic", default=None, help="MQTT subscription filter")
    args = p.parse_args()

    service, app = build_service(args)

    mode = "DEMO(simulator)" if service.cfg.demo else f"MQTT {service.cfg.mqtt.host}:{service.cfg.mqtt.port}"
    print(f"[ew11-analyzer] mode={mode}  data={service.data_dir}  http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
