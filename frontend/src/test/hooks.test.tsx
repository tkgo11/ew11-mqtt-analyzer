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
    vi.useRealTimers();
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

  it("rehydrates history after reconnect and removes stale rows", async () => {
    let resolveInitialHistory!: (value: { packets: PacketDto[] }) => void;
    const initialHistory = new Promise<{ packets: PacketDto[] }>((resolve) => {
      resolveInitialHistory = resolve;
    });
    const packets = vi.spyOn(api, "packets")
      .mockReturnValueOnce(initialHistory)
      .mockResolvedValueOnce({ packets: [] });
    const { result } = renderHook(() => usePacketStream());

    await waitFor(() => expect(api.packets).toHaveBeenCalledTimes(1));
    act(() => MockWebSocket.instance.emit({ type: "packet", data: packet(1) }));
    expect(result.current.packets.map((p) => p.seq)).toEqual([1]);
    vi.useFakeTimers();
    act(() => MockWebSocket.instance.onclose?.());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(packets).toHaveBeenCalledTimes(2);
    expect(result.current.packets).toEqual([]);
    await act(async () => {
      resolveInitialHistory({ packets: [packet(1)] });
      await initialHistory;
    });
    expect(result.current.packets).toEqual([]);
  });

  it("keeps buffered packets when resuming", async () => {
    vi.spyOn(api, "packets").mockResolvedValue({ packets: [] });
    const { result } = renderHook(() => usePacketStream());

    await waitFor(() => expect(api.packets).toHaveBeenCalled());
    act(() => result.current.setPaused(true));
    act(() => MockWebSocket.instance.emit({ type: "packet", data: packet(1) }));
    expect(result.current.buffered).toBe(1);

    act(() => result.current.resume());

    expect(result.current.packets.map((p) => p.seq)).toEqual([1]);
    expect(result.current.buffered).toBe(0);
  });

  it("tracks paused packets, tolerates malformed messages, and handles server clears", async () => {
    let resolveHistory!: (value: { packets: PacketDto[] }) => void;
    const history = new Promise<{ packets: PacketDto[] }>((resolve) => {
      resolveHistory = resolve;
    });
    vi.spyOn(api, "packets").mockReturnValue(history);
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
    await act(async () => {
      resolveHistory({ packets: [packet(2)] });
      await history;
    });
    expect(result.current.packets).toEqual([]);
  });
});
