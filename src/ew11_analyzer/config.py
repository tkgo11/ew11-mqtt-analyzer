"""Application configuration, persisted to JSON in the data dir."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .ai import AiConfig


@dataclass
class MqttConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic: str = "#"  # subscription filter, e.g. 'ew11/#' or 'homenet/#'
    tls: bool = False
    client_id: str = "ew11-analyzer"


@dataclass
class AnalysisConfig:
    prefix_len: int = 3  # signature prefix bytes (STX+LEN+DST separates cmd vs broadcast)
    event_pre: float = 0.3  # seconds before a marker included in its window
    event_post: float = 1.5  # seconds after a marker
    max_packets: int = 200_000  # storage ring cap
    demo_speed: float = 1.0  # simulator interval multiplier


@dataclass
class AppConfig:
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    ai: AiConfig = field(default_factory=AiConfig)
    demo: bool = False


def _update(obj: Any, values: dict[str, Any]) -> None:
    for k, v in values.items():
        if hasattr(obj, k) and not k.startswith("_"):
            setattr(obj, k, v)


def load_config(data_dir: Path) -> AppConfig:
    cfg = AppConfig()
    path = data_dir / "config.json"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw.get("mqtt"), dict):
                _update(cfg.mqtt, raw["mqtt"])
            if isinstance(raw.get("analysis"), dict):
                _update(cfg.analysis, raw["analysis"])
            if isinstance(raw.get("ai"), dict):
                _update(cfg.ai, raw["ai"])
            cfg.demo = bool(raw.get("demo", cfg.demo))
        except (json.JSONDecodeError, OSError):
            pass
    if os.environ.get("EW11_DEMO"):
        cfg.demo = True
    return cfg


def save_config(data_dir: Path, cfg: AppConfig) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "config.json"
    tmp = data_dir / "config.json.tmp"
    payload = {
        "mqtt": asdict(cfg.mqtt),
        "analysis": asdict(cfg.analysis),
        "ai": asdict(cfg.ai),
        "demo": cfg.demo,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)  # contains API key
    tmp.replace(path)


def sanitized_config(cfg: AppConfig) -> dict[str, Any]:
    return {
        "mqtt": {
            "host": cfg.mqtt.host,
            "port": cfg.mqtt.port,
            "username": cfg.mqtt.username,
            "has_password": bool(cfg.mqtt.password),
            "topic": cfg.mqtt.topic,
            "tls": cfg.mqtt.tls,
            "client_id": cfg.mqtt.client_id,
        },
        "analysis": asdict(cfg.analysis),
        "ai": cfg.ai.sanitized(),
        "demo": cfg.demo,
    }
