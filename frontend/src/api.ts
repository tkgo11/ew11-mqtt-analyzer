import type { ConfigDto } from "./types";

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const d = await res.json();
      msg = d.error || d.detail || msg;
    } catch {
      /* keep status text */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => req<import("./types").StatusDto>("GET", "/api/status"),
  packets: (limit = 300, beforeSeq?: number, topic?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (beforeSeq) q.set("before_seq", String(beforeSeq));
    if (topic) q.set("topic", topic);
    return req<{ packets: import("./types").PacketDto[] }>("GET", `/api/packets?${q}`);
  },
  clearPackets: () => req<{ ok: boolean }>("POST", "/api/packets/clear"),
  markers: () => req<{ markers: import("./types").MarkerDto[] }>("GET", "/api/markers"),
  addMarker: (label: string) => req<import("./types").MarkerDto>("POST", "/api/markers", { label }),
  delMarker: (id: number) => req<{ ok: boolean }>("DELETE", `/api/markers/${id}`),
  demoEvent: (kind: string) => req<{ ok: boolean; sent: number }>("POST", "/api/demo/event", { kind }),
  analysis: () => req<import("./types").AnalysisDto>("GET", "/api/analysis"),
  reportText: async (format: "md" | "json") => {
    const res = await fetch(`/api/report?format=${format}`);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.text();
  },
  aiAnalyze: (body: {
    provider?: string;
    base_url?: string;
    api_key?: string;
    model?: string;
    save?: boolean;
  }) => req<{ ok: boolean; text: string }>("POST", "/api/ai/analyze", body),
  config: () => req<ConfigDto>("GET", "/api/config"),
  putConfig: (body: Partial<{ mqtt: object; analysis: object; ai: object; demo: boolean }>) =>
    req<{ ok: boolean; config: ConfigDto }>("PUT", "/api/config", body),
  reconnect: () => req<{ ok: boolean }>("POST", "/api/source/reconnect"),
};

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws`;
}
