"""Integration test against a real MQTT broker.

Skipped unless MOSQUITTO_HOST is set (CI provides an eclipse-mosquitto
service container; locally: `docker run -p 1883:1883 eclipse-mosquitto`).
"""

from __future__ import annotations

import asyncio
import os
import time

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.enums import CallbackAPIVersion

from ew11_analyzer.config import AppConfig, MqttConfig
from ew11_analyzer.pipeline import AnalyzerService

MQTT_HOST = os.environ.get("MOSQUITTO_HOST", "")
MQTT_PORT = int(os.environ.get("MOSQUITTO_PORT", "1883"))
pytestmark = pytest.mark.skipif(not MQTT_HOST, reason="no broker (set MOSQUITTO_HOST)")


async def test_end_to_end_mqtt(tmp_path):
    cfg = AppConfig(
        demo=False,
        mqtt=MqttConfig(host=MQTT_HOST, port=MQTT_PORT, topic="ew11/test/#"),
    )
    svc = AnalyzerService(cfg, tmp_path)
    await svc.start()
    try:
        pub = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        pub.connect(MQTT_HOST, MQTT_PORT)
        pub.loop_start()
        deadline = time.time() + 8
        while time.time() < deadline:
            pub.publish("ew11/test/recv", "F7 08 40 01 51 00 18 EE")
            await asyncio.sleep(0.1)
            svc.storage.flush()
            if svc.storage.count() >= 3:
                break
        pub.loop_stop()
        assert svc.storage.count() >= 3
        pkts = svc.storage.query()
        assert pkts[0].payload == bytes.fromhex("F708400151 0018".replace(" ", ""))
        assert svc.status()["status"] in {"connected", "connecting"}
    finally:
        await svc.stop()
