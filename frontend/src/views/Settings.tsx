import { useEffect, useState } from "react";
import { api } from "../api";
import type { ConfigDto } from "../types";

export function Settings({ toast }: { toast: (m: string) => void }) {
  const [cfg, setCfg] = useState<ConfigDto | null>(null);
  const [mqtt, setMqtt] = useState({ host: "", port: 1883, username: "", password: "", topic: "#", tls: false });
  const [an, setAn] = useState({ prefix_len: 3, event_pre: 0.3, event_post: 1.5, max_packets: 200000 });
  const [ai, setAi] = useState({ provider: "openai", base_url: "", model: "", api_key: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      setMqtt({ host: c.mqtt.host, port: c.mqtt.port, username: c.mqtt.username, password: "", topic: c.mqtt.topic, tls: c.mqtt.tls });
      setAn({
        prefix_len: c.analysis.prefix_len,
        event_pre: c.analysis.event_pre,
        event_post: c.analysis.event_post,
        max_packets: c.analysis.max_packets,
      });
      setAi({ provider: c.ai.provider, base_url: c.ai.base_url, model: c.ai.model, api_key: "" });
    });
  }, []);

  if (!cfg) return <p className="hint">불러오는 중…</p>;

  const save = async (reconnect = false) => {
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        mqtt: { ...mqtt, ...(mqtt.password ? {} : { password: undefined }) },
        analysis: an,
      };
      if (ai.api_key) body.ai = ai;
      else body.ai = { provider: ai.provider, base_url: ai.base_url, model: ai.model };
      await api.putConfig(body);
      if (reconnect) await api.reconnect();
      toast(reconnect ? "저장하고 재연결했습니다" : "저장했습니다");
    } catch (e) {
      toast(`저장 실패: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  const field = (label: string, node: React.ReactNode) => (
    <div style={{ marginBottom: 10 }}>
      <label className="lbl">{label}</label>
      {node}
    </div>
  );

  return (
    <div className="grid2">
      <div className="card">
        <h3>MQTT 브로커</h3>
        <p className="hint">
          EW11 시리얼 브리지가 publish하는 브로커 주소를 입력하세요. 토픽 필터 예: <code>ew11/#</code>,{" "}
          <code>homenet/#</code>, <code>#</code>(전체).
        </p>
        {field("호스트", <input className="inp" style={{ width: "100%" }} value={mqtt.host} onChange={(e) => setMqtt({ ...mqtt, host: e.target.value })} />)}
        {field("포트", <input className="inp" type="number" value={mqtt.port} onChange={(e) => setMqtt({ ...mqtt, port: Number(e.target.value) })} />)}
        {field("사용자명 (선택)", <input className="inp" style={{ width: "100%" }} value={mqtt.username} onChange={(e) => setMqtt({ ...mqtt, username: e.target.value })} />)}
        {field(
          `비밀번호 ${cfg.mqtt.has_password ? "(저장됨 — 비우면 유지)" : ""}`,
          <input className="inp" type="password" style={{ width: "100%" }} value={mqtt.password} onChange={(e) => setMqtt({ ...mqtt, password: e.target.value })} />
        )}
        {field("구독 토픽", <input className="inp" style={{ width: "100%" }} value={mqtt.topic} onChange={(e) => setMqtt({ ...mqtt, topic: e.target.value })} />)}
        <label className="hint" style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 12 }}>
          <input type="checkbox" checked={mqtt.tls} onChange={(e) => setMqtt({ ...mqtt, tls: e.target.checked })} />
          TLS 사용
        </label>
        <div className="toolbar">
          <button className="btn primary" onClick={() => save(true)} disabled={saving} data-testid="save-reconnect">
            저장 + 재연결
          </button>
          <button className="btn" onClick={() => save(false)} disabled={saving}>
            저장만
          </button>
        </div>
      </div>

      <div>
        <div className="card">
          <h3>분석 파라미터</h3>
          {field(
            "시그니처 접두 바이트 (패밀리 묶기)",
            <input className="inp" type="number" min={1} max={6} value={an.prefix_len} onChange={(e) => setAn({ ...an, prefix_len: Number(e.target.value) })} />
          )}
          {field(
            "이벤트 윈도우 — 마커 이전(초)",
            <input className="inp" type="number" step={0.1} value={an.event_pre} onChange={(e) => setAn({ ...an, event_pre: Number(e.target.value) })} />
          )}
          {field(
            "이벤트 윈도우 — 마커 이후(초)",
            <input className="inp" type="number" step={0.1} value={an.event_post} onChange={(e) => setAn({ ...an, event_post: Number(e.target.value) })} />
          )}
          {field(
            "최대 보관 패킷 수",
            <input className="inp" type="number" value={an.max_packets} onChange={(e) => setAn({ ...an, max_packets: Number(e.target.value) })} />
          )}
          <button className="btn" onClick={() => save(false)} disabled={saving}>
            저장
          </button>
        </div>

        <div className="card">
          <h3>AI API</h3>
          {field(
            "프로바이더",
            <select className="inp" style={{ width: "100%" }} value={ai.provider} onChange={(e) => setAi({ ...ai, provider: e.target.value })}>
              <option value="openai">OpenAI 호환</option>
              <option value="anthropic">Anthropic</option>
            </select>
          )}
          {field("Base URL", <input className="inp" style={{ width: "100%" }} value={ai.base_url} onChange={(e) => setAi({ ...ai, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />)}
          {field("모델", <input className="inp" style={{ width: "100%" }} value={ai.model} onChange={(e) => setAi({ ...ai, model: e.target.value })} />)}
          {field(
            `API 키 ${cfg.ai.has_key ? "(저장됨 — 비우면 유지)" : ""}`,
            <input className="inp" type="password" style={{ width: "100%" }} value={ai.api_key} onChange={(e) => setAi({ ...ai, api_key: e.target.value })} />
          )}
          <button className="btn" onClick={() => save(false)} disabled={saving}>
            저장
          </button>
        </div>

        <div className="card">
          <h3>데이터 관리</h3>
          <button
            className="btn danger"
            onClick={async () => {
              if (confirm("수집된 패킷을 모두 삭제할까요?")) {
                await api.clearPackets();
                toast("패킷을 모두 삭제했습니다");
              }
            }}
          >
            수집 패킷 전체 삭제
          </button>
        </div>
      </div>
    </div>
  );
}
