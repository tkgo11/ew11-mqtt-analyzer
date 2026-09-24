import { useMemo, useState } from "react";
import type { PacketDto } from "../types";
import { familyColor, familySig, fmtTime } from "../util";

interface Props {
  packets: PacketDto[];
  paused: boolean;
  setPaused: (v: boolean) => void;
  resume: () => void;
  clear: () => void;
  buffered: number;
  topics: string[];
  markerTs: number[];
}

export function Monitor({ packets, paused, setPaused, resume, clear, buffered, topics, markerTs }: Props) {
  const [topicFilter, setTopicFilter] = useState("");
  const [textFilter, setTextFilter] = useState("");
  const [dedup, setDedup] = useState(false);
  const [expandSeq, setExpandSeq] = useState<number | null>(null);

  const rows = useMemo(() => {
    let out = packets;
    if (topicFilter) out = out.filter((p) => p.topic === topicFilter);
    if (textFilter) {
      const f = textFilter.replace(/\s/g, "").toUpperCase();
      out = out.filter((p) => p.hex.replace(/\s/g, "").includes(f));
    }
    if (dedup) {
      const seen = new Set<string>();
      out = out.filter((p) => {
        if (seen.has(p.hex)) return false;
        seen.add(p.hex);
        return true;
      });
    }
    return out;
  }, [packets, topicFilter, textFilter, dedup]);

  const nearMarker = (ts: number) => markerTs.some((m) => Math.abs(ts - m) < 1.6);

  return (
    <div>
      <div className="toolbar">
        <button
          className={"btn" + (paused ? " primary" : "")}
          onClick={() => (paused ? resume() : setPaused(true))}
          data-testid="pause-btn"
        >
          {paused ? `재개${buffered ? ` (+${buffered})` : ""}` : "일시정지"}
        </button>
        <button className="btn" onClick={clear}>
          목록 비우기
        </button>
        <select className="inp" value={topicFilter} onChange={(e) => setTopicFilter(e.target.value)}>
          <option value="">모든 토픽</option>
          {topics.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          className="inp"
          placeholder="HEX 필터 (예: F70A)"
          value={textFilter}
          onChange={(e) => setTextFilter(e.target.value)}
        />
        <label className="hint" style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <input type="checkbox" checked={dedup} onChange={(e) => setDedup(e.target.checked)} />
          중복 제거
        </label>
        <span className="spacer" />
        <span className="hint">{rows.length} 행 표시</span>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="scroll-y">
          <table className="pkt" data-testid="packet-table">
            <thead>
              <tr>
                <th style={{ width: 24 }} />
                <th style={{ width: 110 }}>시각</th>
                <th>토픽</th>
                <th style={{ width: 44 }}>길이</th>
                <th>HEX</th>
                <th style={{ width: 60 }}>형식</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const sig = familySig(p.hex);
                const marked = nearMarker(p.ts);
                return (
                  <tr
                    key={p.seq}
                    className={marked ? "marked-row" : ""}
                    onClick={() => setExpandSeq(expandSeq === p.seq ? null : p.seq)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <span className="fam-dot" style={{ background: familyColor(sig) }} title={sig} />
                    </td>
                    <td className="dim">{fmtTime(p.ts)}</td>
                    <td className="dim">{p.topic}</td>
                    <td className="dim">{p.len}</td>
                    <td className="hex">{p.hex}</td>
                    <td className="dim">{p.fmt}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="dim" style={{ textAlign: "center", padding: 30 }}>
                    수신된 패킷이 없습니다. 브로커 연결/토픽을 확인하세요.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {expandSeq !== null && (
        <div className="card">
          <h3>패킷 #{expandSeq}</h3>
          <div className="mono" style={{ fontSize: 13 }}>
            {rows.find((r) => r.seq === expandSeq)?.raw}
          </div>
        </div>
      )}
      <p className="hint">
        ● 색상 점은 패밀리(시그니처)를 나타냅니다. 노란 행은 이벤트 마커 근처에서 수신된 패킷입니다. 행을 클릭하면 원문을
        볼 수 있습니다.
      </p>
    </div>
  );
}
