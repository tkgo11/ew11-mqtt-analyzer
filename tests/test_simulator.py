from __future__ import annotations

import asyncio

import pytest

from ew11_analyzer.packets import RawMessage
from ew11_analyzer.sources.simulator import EVENT_KINDS, SimulatedWallpad, frame


def test_frame_structure():
    f = frame(0x40, 0x01, 0x51, [0x00])
    assert f[0] == 0xF7
    assert f[1] == len(f)
    assert f[-1] == 0xEE
    # xor of bytes[1:-2] == checksum byte
    chk = 0
    for b in f[1:-2]:
        chk ^= b
    assert chk == f[-2]


async def test_simulator_emits_baseline():
    sim = SimulatedWallpad(speed=0.1, seed=1)
    got: list[RawMessage] = []
    await sim.start(got.append, lambda s: None)
    await asyncio.sleep(0.6)
    await sim.stop()
    assert len(got) >= 4  # several periodic families
    assert all(m.topic == "ew11/recv" for m in got)


async def test_inject_event():
    sim = SimulatedWallpad(speed=0.1, seed=1)
    got: list[RawMessage] = []
    await sim.start(got.append, lambda s: None)
    sent = await sim.inject_event("light_on")
    await asyncio.sleep(0.05)
    await sim.stop()
    assert sent == 2
    # baseline traffic interleaves; find the command frame by dst=HOST direction
    cmds = [m.payload for m in got if len(m.payload) > 3 and m.payload[2] == 0x01]
    assert cmds, "no command frame emitted"
    assert cmds[0][4] == 0x11  # light cmd


async def test_inject_unknown_kind():
    sim = SimulatedWallpad(seed=1)
    await sim.start(lambda m: None, lambda s: None)
    with pytest.raises(ValueError):
        await sim.inject_event("nope")
    await sim.stop()


def test_event_kinds_known():
    assert "light_on" in EVENT_KINDS
    assert all(isinstance(v, str) for v in EVENT_KINDS.values())
