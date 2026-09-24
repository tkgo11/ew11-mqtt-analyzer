import type { ByteStatDto } from "./types";

/** Family signature from a spaced hex string, mirroring backend signature(). */
export function familySig(hex: string, prefixLen = 3): string {
  const bytes = hex.trim().split(/\s+/).filter(Boolean);
  const head = bytes.slice(0, prefixLen).join("");
  return `${head}:${bytes.length}`;
}

/** Deterministic hue for a family signature -> pleasant pastel dot color. */
export function familyColor(sig: string): string {
  let h = 0;
  for (let i = 0; i < sig.length; i++) h = (h * 31 + sig.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360} 65% 60%)`;
}

export const ROLE_META: Record<string, { ko: string; color: string }> = {
  header: { ko: "헤더", color: "#64748b" },
  const: { ko: "고정", color: "#3b82f6" },
  tail: { ko: "꼬리", color: "#14b8a6" },
  checksum: { ko: "체크섬", color: "#f59e0b" },
  counter: { ko: "카운터", color: "#a78bfa" },
  state: { ko: "상태", color: "#4ade80" },
  data: { ko: "데이터", color: "#f87171" },
};

export function roleMeta(role: string): { ko: string; color: string } {
  return ROLE_META[role] ?? { ko: role, color: "#94a3b8" };
}

/** Byte cell background: role color, intensity scaled by entropy for data bytes. */
export function byteCellStyle(b: ByteStatDto): React.CSSProperties {
  const meta = roleMeta(b.role);
  const alpha = b.role === "data" ? 0.25 + Math.min(b.entropy / 8, 1) * 0.55 : 0.55;
  return { backgroundColor: meta.color, opacity: alpha };
}

export const VERDICT_META: Record<string, { ko: string; cls: string }> = {
  IDLE: { ko: "주기 신호", cls: "badge-idle" },
  EVENT: { ko: "이벤트", cls: "badge-event" },
  MIXED: { ko: "혼합", cls: "badge-mixed" },
  UNKNOWN: { ko: "미분류", cls: "badge-unknown" },
};

export function verdictMeta(v: string): { ko: string; cls: string } {
  return VERDICT_META[v] ?? { ko: v, cls: "badge-unknown" };
}

export function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

export function fmtDateTime(ts: number): string {
  const d = new Date(ts * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function fmtInterval(s: number | null): string {
  if (s === null) return "-";
  if (s < 0.01) return `${(s * 1000).toFixed(1)}ms`;
  if (s < 60) return `${s.toFixed(2)}s`;
  return `${(s / 60).toFixed(1)}min`;
}

/** highlight diff positions inside a spaced hex string */
export function hexWithDiff(hex: string, positions: number[]): { text: string; changed: boolean }[] {
  return hex
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((text, i) => ({ text, changed: positions.includes(i) }));
}

export function download(filename: string, text: string, mime = "text/markdown") {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
