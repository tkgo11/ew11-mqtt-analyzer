"""Built-in wallpad simulator (demo / E2E mode).

Emulates a Korean wallpad RS485 bus bridged to MQTT: constant periodic status
broadcasts (the "idle" traffic) plus command/ack packets that can be injected
on demand to simulate a button press.

Frame format (typical wallpad style):
    F7 LEN DST SRC CMD DATA... CHK EE
    LEN = total frame length, CHK = XOR of bytes [1 .. len-2]
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from functools import reduce
from operator import xor

from ..packets import RawMessage
from .base import EmitFn, StatusFn

STX, ETX = 0xF7, 0xEE
WALLPAD, HOST = 0x40, 0x01

TOPIC = "ew11/recv"

# event kinds exposed to the API / UI
EVENT_KINDS: dict[str, str] = {
    "light_on": "거실 조명 켜기",
    "light_off": "거실 조명 끄기",
    "heat_set": "난방 온도 설정",
    "vent": "환기 토글",
    "gas": "가스 밸브 확인",
    "elevator": "엘리베이터 호출",
}


def _xor(data: bytes | list[int]) -> int:
    return reduce(xor, data, 0)


def frame(dst: int, src: int, cmd: int, data: list[int]) -> bytes:
    body = [dst, src, cmd, *data]
    total = len(body) + 4  # STX + LEN + body + CHK + ETX
    head = bytes([STX, total, *body])
    return head + bytes([_xor(head[1:]), ETX])


class SimulatedWallpad:
    name = "simulator"

    def __init__(self, speed: float = 1.0, seed: int | None = 0):
        self.speed = max(speed, 0.05)
        self._rng = random.Random(seed)
        self._emit: EmitFn | None = None
        self._on_status: StatusFn | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

        # mutable "device" state reflected in periodic broadcasts
        self._counter = 0
        self._lights = [0, 1, 0, 0]
        self._heat_set = 22
        self._heat_cur = 21
        self._heat_mode = 1
        self._vent = 0
        self._energy_wh = 1234

    # ------------------------------------------------------------------ API
    async def start(self, emit: EmitFn, on_status: StatusFn) -> None:
        self._emit = emit
        self._on_status = on_status
        self._running = True
        on_status("connected")
        self._tasks = [
            asyncio.create_task(self._loop(0.9, self._light_status)),
            asyncio.create_task(self._loop(2.1, self._heat_status)),
            asyncio.create_task(self._loop(4.6, self._vent_status)),
            asyncio.create_task(self._loop(6.8, self._energy)),
            asyncio.create_task(self._loop(0.45, self._lobby_poll)),
            asyncio.create_task(self._loop(3.3, self._unknown)),
        ]

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    async def inject_event(self, kind: str) -> int:
        """Emit a command (+ack) as if a physical button was pressed."""
        if self._emit is None:
            return 0
        emit = self._emit
        sent = 0

        def send(f: bytes) -> None:
            nonlocal sent
            emit(RawMessage(ts=time.time(), topic=TOPIC, payload=f))
            sent += 1

        if kind == "light_on":
            send(frame(HOST, WALLPAD, 0x11, [0x01, 0x01, 0xFF]))
            await asyncio.sleep(0.06 * self.speed)
            send(frame(WALLPAD, HOST, 0x91, [0x01, 0x00]))  # ack
            self._lights[0] = 1
        elif kind == "light_off":
            send(frame(HOST, WALLPAD, 0x11, [0x01, 0x01, 0x00]))
            await asyncio.sleep(0.06 * self.speed)
            send(frame(WALLPAD, HOST, 0x91, [0x01, 0x00]))
            self._lights[0] = 0
        elif kind == "heat_set":
            self._heat_set = self._rng.choice([20, 21, 22, 23, 24, 25])
            send(frame(HOST, WALLPAD, 0x21, [0x01, self._heat_set, 0x01]))
            await asyncio.sleep(0.08 * self.speed)
            send(frame(WALLPAD, HOST, 0xA1, [0x01, 0x00]))
        elif kind == "vent":
            self._vent = (self._vent + 1) % 3
            send(frame(HOST, WALLPAD, 0x31, [0x01, self._vent]))
        elif kind == "gas":
            send(frame(HOST, WALLPAD, 0x61, [0x01]))
            await asyncio.sleep(0.05 * self.speed)
            send(frame(WALLPAD, HOST, 0xE1, [0x00]))
        elif kind == "elevator":
            send(frame(HOST, WALLPAD, 0x51, [0xFF]))
            await asyncio.sleep(0.12 * self.speed)
            send(frame(WALLPAD, HOST, 0xD1, [0x01]))
        else:
            raise ValueError(f"unknown event kind: {kind}")
        return sent

    # ------------------------------------------------------------- internals
    def _tx(self, f: bytes) -> None:
        if self._emit:
            self._emit(RawMessage(ts=time.time(), topic=TOPIC, payload=f))

    async def _loop(self, interval: float, make: Callable[[], bytes]) -> None:
        try:
            while self._running:
                self._counter = (self._counter + 1) & 0xFF
                self._tx(make())
                jitter = self._rng.uniform(-0.04, 0.04)
                await asyncio.sleep(max(0.05, (interval + jitter) * self.speed))
        except asyncio.CancelledError:
            pass

    # periodic "idle" traffic ---------------------------------------------
    def _light_status(self) -> bytes:
        return frame(WALLPAD, HOST, 0x11, [*self._lights, self._counter & 0xFF])

    def _heat_status(self) -> bytes:
        drift = self._rng.choice([0, 0, 0, 1, -1])
        self._heat_cur = min(max(self._heat_cur + drift, 15), 30)
        return frame(WALLPAD, HOST, 0x21, [0x01, self._heat_set, self._heat_cur, self._heat_mode])

    def _vent_status(self) -> bytes:
        return frame(WALLPAD, HOST, 0x31, [self._vent, 0x00])

    def _energy(self) -> bytes:
        self._energy_wh += self._rng.randint(0, 9)
        return frame(
            WALLPAD,
            HOST,
            0x41,
            [
                (self._energy_wh >> 8) & 0xFF,
                self._energy_wh & 0xFF,
                self._rng.randint(0, 255),
                0x00,
                self._rng.randint(0, 5),
                0x00,
            ],
        )

    def _lobby_poll(self) -> bytes:
        return frame(WALLPAD, HOST, 0x51, [0x00])

    def _unknown(self) -> bytes:
        return frame(WALLPAD, HOST, 0x71, [self._counter & 0xFF, self._rng.randint(0, 3), 0xAA])
