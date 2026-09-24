import { useState } from "react";
import { api } from "../api";
import { ByteMap } from "../components/ByteMap";
import type { AnalysisDto, FamilyDto } from "../types";
import { fmtDateTime, fmtInterval, hexWithDiff, verdictMeta } from "../util";

function FamilyCard({ f }: { f: FamilyDto }) {
  const [open, setOpen] = useState(false);
  const v = f.verdict;
  const vm = verdictMeta(v.verdict);
  return (
    <div className="family-card" data-testid={`family-${f.sig}`}>
      <div className="family-head" onClick={() => setOpen(!open)}>
        <span className="sig mono">{f.sig}</span>
        <span className={`badge ${vm.cls}`}>{vm.ko}</span>
        <span className="stat">{v.count}개</span>
        <span className="stat">{v.rate_per_min}/분</span>
        <span className="stat dim">주기성</span>
        <span className="meter">
          <i style={{ width: `${Math.round(v.periodicity * 100)}%` }} />
        </span>
        {v.event_lift !== null && <span className="stat">lift {v.event_lift >= 99 ? "∞" : v.event_lift.toFixed(1)}</span>}
        {f.checksum && (
          <span className="chip mono" title={`일치율 ${Math.round(f.checksum.rate * 100)}%`}>
            chk:{f.checksum.algo}
          </span>
        )}
        <span className="stat dim">신뢰도 {Math.round(v.confidence * 100)}%</span>
      </div>
      {open && (
        <div className="family-body">
          <dl className="kv">
            <dt>토픽</dt>
            <dd>{v.topics.join(", ")}</dd>
            <dt>평균 간격</dt>
            <dd>{fmtInterval(v.mean_interval)}</dd>
            <dt>기준/이벤트</dt>
            <dd>
              {v.baseline_count}회 / 윈도우 내 {v.event_count}회
            </dd>
            {v.marker_ids.length > 0 && (
              <>
                <dt>연관 마커</dt>
                <dd>{v.marker_ids.map((i) => `#${i}`).join(", ")}</dd>
              </>
            )}
          </dl>
          <ByteMap bytes={f.bytemap} checksum={f.checksum} />
          <h4 style={{ margin: "10px 0 6px", fontSize: 12, color: "var(--text-dim)" }}>샘플</h4>
          <div className="samples">
            {f.samples.map((s, i) => (
              <div className="row" key={i}>
                {s}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function Analysis({ toast }: { toast: (m: string) => void }) {
  const [data, setData] = useState<AnalysisDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>("");

  const run = async () => {
    setLoading(true);
    try {
      setData(await api.analysis());
    } catch (e) {
      toast(`분석 실패: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const families = (data?.families ?? []).filter((f) => !filter || f.verdict.verdict === filter);

  return (
    <div>
      <div className="toolbar">
        <button className="btn primary" onClick={run} disabled={loading} data-testid="run-analysis">
          {loading ? "분석 중…" : "분석 실행"}
        </button>
        {data && (
          <>
            <span className="chip">
              패킷 {data.total_packets}개 · 패밀리 {data.total_families}개 · {fmtDateTime(data.started_at)} ~{" "}
              {fmtDateTime(data.ended_at)}
            </span>
            <span className="spacer" />
            <select className="inp" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">전체 판정</option>
              <option value="EVENT">이벤트만</option>
              <option value="IDLE">주기 신호만</option>
              <option value="MIXED">혼합</option>
              <option value="UNKNOWN">미분류</option>
            </select>
          </>
        )}
      </div>

      {data?.notes.map((n, i) => (
        <div className="note" key={i}>
          {n}
        </div>
      ))}

      {!data && (
        <div className="card">
          <p className="hint">
            <b>사용법:</b> 1) '이벤트 표시' 탭에서 월패드 버튼을 누를 때마다 마커를 기록 → 2) 여기서 '분석 실행' →
            3) <span className="badge badge-event">이벤트</span>로 분류된 패밀리가 명령/응답 패킷입니다.{" "}
            <span className="badge badge-idle">주기 신호</span>는 평소에도 흐르는 상태 브로드캐스트입니다.
          </p>
        </div>
      )}

      {families.map((f) => (
        <FamilyCard key={f.sig} f={f} />
      ))}

      {data && data.diffs.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>마커별 차이 분석 (무엇이 달라졌나)</h3>
          {data.diffs.map((d) => (
            <div key={d.marker.id} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>
                #{d.marker.id} {d.marker.label} <span className="dim mono">{fmtDateTime(d.marker.ts)}</span>
              </div>
              {d.hits.length === 0 && <p className="hint">윈도우 내 패킷 없음</p>}
              {d.hits.slice(0, 6).map((h) => (
                <div key={h.sig} style={{ marginBottom: 8 }}>
                  <code className="mono">{h.sig}</code> ×{h.count_in}
                  {h.novel && <span className="badge badge-event" style={{ marginLeft: 6 }}>신규 패밀리</span>}
                  {h.changed_positions.length > 0 && (
                    <span className="dim">
                      {" "}
                      · 변경 바이트 <span className="diff-pos">{h.changed_positions.map((p) => `[${p}]`).join("")}</span>
                    </span>
                  )}
                  <div className="samples" style={{ marginTop: 4 }}>
                    {h.samples_in.slice(0, 2).map((s, i) => (
                      <div className="row" key={i}>
                        {hexWithDiff(s, h.changed_positions).map((b, j) => (
                          <span key={j} className={"b" + (b.changed ? " changed" : " same")}>
                            {b.text}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
