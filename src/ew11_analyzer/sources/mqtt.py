"""Live MQTT source (paho-mqtt)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from ..config import MqttConfig
from ..packets import RawMessage
from .base import EmitFn, StatusFn


class MqttSource:
    name = "mqtt"

    def __init__(self, cfg: MqttConfig):
        self.cfg = cfg
        self._client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._emit: EmitFn | None = None
        self._on_status: StatusFn | None = None
        self._stopping = False

    async def start(self, emit: EmitFn, on_status: StatusFn) -> None:
        self._emit = emit
        self._on_status = on_status
        self._loop = asyncio.get_running_loop()
        self._stopping = False

        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.cfg.client_id,
            protocol=mqtt.MQTTv311,
        )
        if self.cfg.username:
            client.username_pw_set(self.cfg.username, self.cfg.password or None)
        if self.cfg.tls:
            client.tls_set()

        client.on_connect = self._handle_connect
        client.on_message = self._handle_message
        client.on_disconnect = self._handle_disconnect

        self._client = client
        self._status("connecting")
        # paho runs its own network thread; connect_async + loop_start is
        # non-blocking and auto-reconnects.
        client.connect_async(self.cfg.host, self.cfg.port, keepalive=30)
        client.loop_start()

    def _status(self, s: str) -> None:
        if self._on_status and self._loop:
            self._loop.call_soon_threadsafe(self._on_status, s)

    def _handle_connect(
        self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if int(reason_code) == 0:
            self._status("connected")
            client.subscribe(self.cfg.topic or "#")
        else:
            self._status(f"connect_failed:{reason_code}")

    def _handle_disconnect(
        self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if not self._stopping:
            self._status("disconnected")

    def _handle_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if self._emit and self._loop:
            raw = RawMessage(ts=time.time(), topic=msg.topic, payload=bytes(msg.payload))
            self._loop.call_soon_threadsafe(self._emit, raw)

    async def stop(self) -> None:
        self._stopping = True
        client = self._client
        self._client = None
        if client is not None:
            await asyncio.to_thread(self._stop_blocking, client)

    @staticmethod
    def _stop_blocking(client: mqtt.Client) -> None:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
