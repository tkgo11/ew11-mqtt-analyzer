"""Application configuration, persisted to JSON in the data dir."""

from __future__ import annotations

import contextlib
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
            current = getattr(obj, k)
            if isinstance(current, bool):
                valid = isinstance(v, bool)
            elif isinstance(current, int):
                valid = isinstance(v, int) and not isinstance(v, bool)
            elif isinstance(current, float):
                valid = isinstance(v, int | float) and not isinstance(v, bool)
            else:
                valid = isinstance(v, type(current))
            if valid:
                setattr(obj, k, float(v) if isinstance(current, float) else v)


def _normalize_mqtt(cfg: MqttConfig, defaults: MqttConfig) -> None:
    if not cfg.host:
        cfg.host = defaults.host
    if not 1 <= cfg.port <= 65535:
        cfg.port = defaults.port
    if not cfg.topic:
        cfg.topic = defaults.topic
    if not cfg.client_id:
        cfg.client_id = defaults.client_id


def _normalize_analysis(cfg: AnalysisConfig, defaults: AnalysisConfig) -> None:
    if not 1 <= cfg.prefix_len <= 32:
        cfg.prefix_len = defaults.prefix_len
    if not 0 <= cfg.event_pre <= 3600:
        cfg.event_pre = defaults.event_pre
    if not 0 <= cfg.event_post <= 3600:
        cfg.event_post = defaults.event_post
    if not 100 <= cfg.max_packets <= 10_000_000:
        cfg.max_packets = defaults.max_packets
    if not 0.05 <= cfg.demo_speed <= 100:
        cfg.demo_speed = defaults.demo_speed


def _normalize_ai(cfg: AiConfig, defaults: AiConfig) -> None:
    if cfg.provider not in {"openai", "anthropic"}:
        cfg.provider = defaults.provider
    if not cfg.base_url:
        cfg.base_url = defaults.base_url
    if not cfg.model:
        cfg.model = defaults.model
    if not 1 <= cfg.max_tokens <= 1_000_000:
        cfg.max_tokens = defaults.max_tokens


def _normalize(cfg: AppConfig) -> None:
    defaults = AppConfig()
    _normalize_mqtt(cfg.mqtt, defaults.mqtt)
    _normalize_analysis(cfg.analysis, defaults.analysis)
    _normalize_ai(cfg.ai, defaults.ai)


def load_config(data_dir: Path) -> AppConfig:
    cfg = AppConfig()
    path = data_dir / "config.json"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                if isinstance(raw.get("mqtt"), dict):
                    _update(cfg.mqtt, raw["mqtt"])
                if isinstance(raw.get("analysis"), dict):
                    _update(cfg.analysis, raw["analysis"])
                if isinstance(raw.get("ai"), dict):
                    _update(cfg.ai, raw["ai"])
                if isinstance(raw.get("demo"), bool):
                    cfg.demo = raw["demo"]
        except (json.JSONDecodeError, OSError):
            pass
    _normalize(cfg)
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
    # contains the API key; filesystems without POSIX mode bits (FAT32, Windows
    # ACLs) raise OSError — best-effort hardening only
    with contextlib.suppress(OSError):
        tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
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
