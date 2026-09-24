"""Packet source interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..packets import RawMessage

EmitFn = Callable[[RawMessage], None]
StatusFn = Callable[[str], None]


class PacketSource(Protocol):
    """A source of raw packets. Implementations push via ``emit``."""

    name: str

    async def start(self, emit: EmitFn, on_status: StatusFn) -> None: ...

    async def stop(self) -> None: ...
