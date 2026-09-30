from __future__ import annotations

import json

from ew11_analyzer.config import load_config


def test_load_config_ignores_non_object_json(tmp_path):
    (tmp_path / "config.json").write_text("[]", encoding="utf-8")

    cfg = load_config(tmp_path)

    assert cfg.mqtt.port == 1883
    assert cfg.demo is False


def test_load_config_rejects_invalid_types_and_ranges(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "mqtt": {"host": 42, "port": -1, "tls": "yes"},
                "analysis": {"prefix_len": 0, "event_pre": "wide", "max_packets": 1},
                "ai": {"provider": "unknown", "max_tokens": 0},
                "demo": "yes",
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(tmp_path)

    assert cfg.mqtt.host == "127.0.0.1"
    assert cfg.mqtt.port == 1883
    assert cfg.mqtt.tls is False
    assert cfg.analysis.prefix_len == 3
    assert cfg.analysis.event_pre == 0.3
    assert cfg.analysis.max_packets == 200_000
    assert cfg.ai.provider == "openai"
    assert cfg.ai.max_tokens == 4096
    assert cfg.demo is False
