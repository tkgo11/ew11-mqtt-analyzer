import { useState } from "react";
import { api } from "../api";
import type { MarkerDto, StatusDto } from "../types";
import { fmtTime } from "../util";

const PRESETS = ["조명 켜기", "조명 끄기", "난방 조절", "환기", "가스밸브", "엘리베이터", "현관문", "기타"];

export function Marking({
  markers,
  onMarkersChanged,
  status,
  toast,
}: {
  markers: MarkerDto[];
  onMarkersChanged: () => void;
  status: StatusDto | null;
  toast: (msg: string) => void;
}) {
  const [label, setLabel] = useState("조명 켜기");
  const [busy, setBusy] = useState(false);

  const mark = async () => {
    setBusy(true);
    try {
      await api.addMarker(label);
      onMarkersChanged();
      toast(`마커 기록됨: ${label}`);
    } finally {
      setBusy(false);
    }
  };

  const del = async (id: number) => {
    await api.delMarker(id);
    onMarkersChanged();
  };

  const demoEvents = status?.demo_events ?? null;

  return (
    <div className="grid2">
      <div className="card">
        <h3>이벤트 표시</h3>
        <p className="hint">
          월패드에서 <b>실제 버튼을 누르는 순간</b> 아래 버튼을 누르세요. 해당 시각 ±이벤트 윈도우 안의 패킷만 모아
          기준선(평소 트래픽)과 비교해 명령 패킷을 찾아냅니다. 같은 버튼을 3~5회 반복하면 정확도가 올라갑니다.
        </p>
        <div className="preset-chips" style={{ marginBottom: 12 }}>
          {PRESETS.map((p) => (
            <span key={p} className={"chip" + (label === p ? " on" : "")} onClick={() => setLabel(p)}>
              {p}
            </span>
          ))}
        </div>
        <input
          className="inp"
          style={{ width: "100%", marginBottom: 14 }}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="이벤트 라벨 (예: 거실 조명 켜기)"
        />
        <button className="btn big" onClick={mark} disabled={busy} data-testid="mark-btn">
          지금 이벤트 표시
        </button>
      </div>

      <div>
        {demoEvents && (
          <div className="card">
            <h3>시뮬레이터 이벤트 (데모 모드)</h3>
            <p className="hint">실제 월패드 없이 동작을 시험해 볼 수 있습니다. 버튼을 누르면 가상 명령 패킷이 주입됩니다.</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {Object.entries(demoEvents).map(([kind, ko]) => (
                <button
                  key={kind}
                  className="btn"
                  data-testid={`demo-${kind}`}
                  onClick={async () => {
                    await api.demoEvent(kind);
                    toast(`시뮬레이터 이벤트 발생: ${ko}`);
                  }}
                >
                  {ko}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="card">
          <h3>기록된 마커 ({markers.length})</h3>
          {markers.length === 0 && <p className="hint">아직 마커가 없습니다.</p>}
          {markers
            .slice()
            .reverse()
            .map((m) => (
              <div key={m.id} className="marker-row">
                <span className="mono dim">#{m.id}</span>
                <span className="mono">{fmtTime(m.ts)}</span>
                <span>{m.label}</span>
                <span className="spacer" style={{ flex: 1 }} />
                <button className="btn danger" onClick={() => del(m.id)}>
                  삭제
                </button>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
