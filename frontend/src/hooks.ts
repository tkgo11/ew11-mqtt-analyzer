import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "./api";
import type { PacketDto, StatusDto, WsMsg } from "./types";

const MAX_ROWS = 600;

function mergePackets(...groups: PacketDto[][]): PacketDto[] {
  const bySeq = new Map<number, PacketDto>();
  for (const group of groups) {
    for (const packet of group) bySeq.set(packet.seq, packet);
  }
  return [...bySeq.values()].sort((a, b) => b.seq - a.seq).slice(0, MAX_ROWS);
}

/** Live packet stream over WebSocket with pause buffering. */
export function usePacketStream() {
  const [packets, setPackets] = useState<PacketDto[]>([]);
  const [connStatus, setConnStatus] = useState<string>("connecting");
  const [paused, setPaused] = useState(false);
  const [buffered, setBuffered] = useState(0);
  const pausedRef = useRef(false);
  const bufRef = useRef<PacketDto[]>([]);
  const dataVersionRef = useRef(0);
  pausedRef.current = paused;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let dead = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onmessage = (ev) => {
        let parsed: unknown;
        try {
          parsed = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (typeof parsed !== "object" || parsed === null || !("type" in parsed)) return;
        const msg = parsed as WsMsg;
        if (msg.type === "packet" && msg.data && typeof msg.data.seq === "number") {
          if (pausedRef.current) {
            bufRef.current.push(msg.data);
            if (bufRef.current.length > MAX_ROWS) bufRef.current.splice(0, bufRef.current.length - MAX_ROWS);
            setBuffered(bufRef.current.length);
          } else {
            setPackets((prev) => mergePackets(prev, [msg.data]));
          }
        } else if (msg.type === "status" && msg.data && typeof msg.data.status === "string") {
          setConnStatus(msg.data.status);
        } else if (msg.type === "clear") {
          dataVersionRef.current += 1;
          setPackets([]);
          bufRef.current = [];
          setBuffered(0);
        }
      };
      ws.onclose = () => {
        setConnStatus("disconnected");
        if (!dead) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    const loadVersion = dataVersionRef.current;
    api.packets(MAX_ROWS).then(({ packets: stored }) => {
      if (!dead && dataVersionRef.current === loadVersion) {
        setPackets((live) => mergePackets(stored, live));
      }
    }).catch(() => {});
    return () => {
      dead = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  const resume = useCallback(() => {
    setPaused(false);
    if (bufRef.current.length) {
      setPackets((prev) => mergePackets(prev, bufRef.current));
      bufRef.current = [];
    }
    setBuffered(0);
  }, []);

  const clear = useCallback(() => {
    dataVersionRef.current += 1;
    setPackets([]);
    bufRef.current = [];
    setBuffered(0);
  }, []);

  return { packets, connStatus, paused, setPaused, resume, clear, buffered };
}

/** Poll /api/status; wsConnStatus overrides the displayed status when fresher. */
export function useStatus(intervalMs = 3000) {
  const [status, setStatus] = useState<StatusDto | null>(null);
  useEffect(() => {
    let dead = false;
    const tick = async () => {
      try {
        const s = await api.status();
        if (!dead) setStatus(s);
      } catch {
        /* backend may be restarting */
      }
    };
    tick();
    const t = setInterval(tick, intervalMs);
    return () => {
      dead = true;
      clearInterval(t);
    };
  }, [intervalMs]);
  return status;
}
