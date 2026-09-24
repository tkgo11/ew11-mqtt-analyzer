import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "./api";
import type { PacketDto, StatusDto, WsMsg } from "./types";

const MAX_ROWS = 600;

/** Live packet stream over WebSocket with pause buffering. */
export function usePacketStream() {
  const [packets, setPackets] = useState<PacketDto[]>([]);
  const [connStatus, setConnStatus] = useState<string>("connecting");
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const bufRef = useRef<PacketDto[]>([]);
  pausedRef.current = paused;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let dead = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as WsMsg;
        if (msg.type === "packet") {
          if (pausedRef.current) {
            bufRef.current.push(msg.data);
          } else {
            setPackets((prev) => {
              const next = [msg.data, ...prev];
              return next.length > MAX_ROWS ? next.slice(0, MAX_ROWS) : next;
            });
          }
        } else if (msg.type === "status") {
          setConnStatus(msg.data.status);
        }
      };
      ws.onclose = () => {
        setConnStatus("disconnected");
        if (!dead) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      dead = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  const resume = useCallback(() => {
    setPaused(false);
    if (bufRef.current.length) {
      setPackets((prev) => [...bufRef.current.reverse(), ...prev].slice(0, MAX_ROWS));
      bufRef.current = [];
    }
  }, []);

  const clear = useCallback(() => {
    setPackets([]);
    bufRef.current = [];
  }, []);

  return { packets, connStatus, paused, setPaused, resume, clear, buffered: bufRef.current.length };
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
