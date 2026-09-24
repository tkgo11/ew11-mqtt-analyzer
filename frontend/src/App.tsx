import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { usePacketStream, useStatus } from "./hooks";
import type { MarkerDto } from "./types";
import { Analysis } from "./views/Analysis";
import { Marking } from "./views/Marking";
import { Monitor } from "./views/Monitor";
import { Report } from "./views/Report";
import { Settings } from "./views/Settings";

type Tab = "monitor" | "marking" | "analysis" | "report" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "monitor", label: "실시간 모니터" },
  { id: "marking", label: "이벤트 표시" },
  { id: "analysis", label: "패킷 분석" },
  { id: "report", label: "AI 리포트" },
  { id: "settings", label: "설정" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("monitor");
  const [markers, setMarkers] = useState<MarkerDto[]>([]);
  const [toastMsg, setToastMsg] = useState("");
  const { packets, connStatus, paused, setPaused, resume, clear, buffered } = usePacketStream();
  const status = useStatus();

  const refreshMarkers = useCallback(() => {
    api.markers().then((d) => setMarkers(d.markers)).catch(() => {});
  }, []);
  useEffect(refreshMarkers, [refreshMarkers]);

  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(""), 2500);
  }, []);

  const dotCls =
    connStatus === "connected" ? "on" : connStatus === "connecting" ? "wait" : "off";

  return (
    <>
      <header className="top">
        <div className="logo">
          EW11 패킷 분석기<small>wallpad RS485 → MQTT</small>
        </div>
        <span className="chip">
          <span className={`status-dot ${dotCls}`} />
          {connStatus === "connected" ? "연결됨" : connStatus === "connecting" ? "연결 중…" : "끊김"}
        </span>
        {status && (
          <>
            <span className={"chip" + (status.mode === "demo" ? " demo" : "")}>
              {status.mode === "demo" ? "데모(시뮬레이터)" : `${status.broker}`}
            </span>
            <span className="chip mono">
              {status.total_packets.toLocaleString()} pkts · {status.rate_per_s}/s
            </span>
          </>
        )}
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {tab === "monitor" && (
          <Monitor
            packets={packets}
            paused={paused}
            setPaused={setPaused}
            resume={resume}
            clear={clear}
            buffered={buffered}
            topics={status?.topics ?? []}
            markerTs={markers.map((m) => m.ts)}
          />
        )}
        {tab === "marking" && (
          <Marking markers={markers} onMarkersChanged={refreshMarkers} status={status} toast={toast} />
        )}
        {tab === "analysis" && <Analysis toast={toast} />}
        {tab === "report" && <Report toast={toast} />}
        {tab === "settings" && <Settings toast={toast} />}
      </main>

      {toastMsg && <div className="toast">{toastMsg}</div>}
    </>
  );
}
