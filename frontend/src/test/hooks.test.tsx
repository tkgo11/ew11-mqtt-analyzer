import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { usePacketStream } from "../hooks";
import type { PacketDto } from "../types";

const packet = (seq: number): PacketDto => ({
  seq,
  ts: seq,
  topic: "ew11/recv",
  hex: `AA ${seq.toString(16).padStart(2, "0").toUpperCase()}`,
  len: 2,
  fmt: "raw",
  raw: "",
});

class MockWebSocket {
  static instance: MockWebSocket;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    MockWebSocket.instance = this;
  }

  close() {}

  emit(data: unknown) {
    this.onmessage?.({ data: typeof data === "string" ? data : JSON.stringify(data) } as MessageEvent<string>);
  }
}

describe("usePacketStream", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads stored packets and deduplicates live overlap", async () => {
    vi.spyOn(api, "packets").mockResolvedValue({ packets: [packet(2), packet(1)] });
    const { result } = renderHook(() => usePacketStream());

    await waitFor(() => expect(result.current.packets.map((p) => p.seq)).toEqual([2, 1]));
    act(() => {
      MockWebSocket.instance.emit({ type: "packet", data: packet(2) });
      MockWebSocket.instance.emit({ type: "packet", data: packet(3) });
    });

    expect(result.current.packets.map((p) => p.seq)).toEqual([3, 2, 1]);
  });

  it("tracks paused packets, tolerates malformed messages, and handles server clears", async () => {
    vi.spyOn(api, "packets").mockResolvedValue({ packets: [] });
    const { result } = renderHook(() => usePacketStream());
    await waitFor(() => expect(api.packets).toHaveBeenCalled());

    act(() => result.current.setPaused(true));
    act(() => {
      MockWebSocket.instance.emit("not-json");
      MockWebSocket.instance.emit({ type: "packet", data: packet(1) });
    });
    expect(result.current.buffered).toBe(1);
    expect(result.current.packets).toEqual([]);

    act(() => MockWebSocket.instance.emit({ type: "clear", data: {} }));
    expect(result.current.buffered).toBe(0);
    expect(result.current.packets).toEqual([]);
  });
});
