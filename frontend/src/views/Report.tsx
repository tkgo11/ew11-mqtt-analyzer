import { useEffect, useState } from "react";
import { api } from "../api";
import type { ConfigDto } from "../types";
import { download } from "../util";

export function Report({ toast }: { toast: (m: string) => void }) {
  const [fmt, setFmt] = useState<"md" | "json">("md");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [cfg, setCfg] = useState<ConfigDto | null>(null);
  const [aiText, setAiText] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [showAiCfg, setShowAiCfg] = useState(false);
  const [provider, setProvider] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      setProvider(c.ai.provider);
      setBaseUrl(c.ai.base_url);
      setModel(c.ai.model);
    });
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      setText(await api.reportText(fmt));
    } catch (e) {
      toast(`리포트 생성 실패: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const sendToAi = async () => {
    setAiBusy(true);
    setAiText("");
    try {
      const res = await api.aiAnalyze({
        provider,
        base_url: baseUrl || undefined,
        api_key: apiKey || undefined,
        model: model || undefined,
        save: true,
      });
      setAiText(res.text);
      toast("AI 분석 완료");
    } catch (e) {
      toast(`AI 호출 실패: ${e}`);
      setAiText(`오류: ${e}`);
    } finally {
      setAiBusy(false);
    }
  };

  return (
    <div className="grid2">
      <div>
        <div className="card">
          <h3>AI 분석용 리포트</h3>
          <p className="hint">
            현재까지 수집된 패킷과 자동 분석 결과를 AI가 이해하기 쉬운 형태로 정리합니다. 파일로 저장해
            ChatGPT/Claude에 붙여넣거나, API 키를 설정하면 바로 전송할 수 있습니다.
          </p>
          <div className="toolbar">
            <select className="inp" value={fmt} onChange={(e) => setFmt(e.target.value as "md" | "json")}>
              <option value="md">Markdown (AI 붙여넣기용)</option>
              <option value="json">JSON (기계 판독용)</option>
            </select>
            <button className="btn primary" onClick={load} disabled={loading} data-testid="gen-report">
              {loading ? "생성 중…" : "리포트 생성"}
            </button>
            {text && (
              <>
                <button className="btn" onClick={() => download(`ew11-report.${fmt}`, text, fmt === "json" ? "application/json" : "text/markdown")}>
                  파일 다운로드
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    navigator.clipboard.writeText(text);
                    toast("클립보드에 복사됨");
                  }}
                >
                  복사
                </button>
              </>
            )}
            <a className="btn" href="/api/export.csv" download>
              패킷 CSV 다운로드
            </a>
          </div>
          {text && <pre className="report" data-testid="report-preview">{text.slice(0, 60000)}</pre>}
        </div>
      </div>

      <div>
        <div className="card">
          <h3>AI에게 바로 보내기</h3>
          <p className="hint">
            OpenAI 호환 API(Ollama, LM Studio, OpenRouter 포함) 또는 Anthropic API를 지원합니다. 키는 이 기기의
            로컬 설정 파일에만 저장됩니다.
          </p>
          <div className="toolbar">
            <button className="btn" onClick={() => setShowAiCfg(!showAiCfg)}>
              {showAiCfg ? "설정 접기" : `AI 설정 ${cfg?.ai.has_key ? "(키 저장됨)" : "(키 없음)"}`}
            </button>
            <button className="btn primary" onClick={sendToAi} disabled={aiBusy} data-testid="send-ai">
              {aiBusy ? "분석 요청 중…" : "AI에게 분석 요청"}
            </button>
          </div>
          {showAiCfg && (
            <div style={{ marginBottom: 10 }}>
              <label className="lbl">프로바이더</label>
              <select className="inp" value={provider} onChange={(e) => setProvider(e.target.value)} style={{ width: "100%", marginBottom: 8 }}>
                <option value="openai">OpenAI 호환 (OpenAI/Ollama/LM Studio/OpenRouter)</option>
                <option value="anthropic">Anthropic (Claude)</option>
              </select>
              {provider === "openai" && (
                <>
                  <label className="lbl">Base URL (Ollama: http://localhost:11434/v1)</label>
                  <input className="inp" style={{ width: "100%", marginBottom: 8 }} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
                </>
              )}
              <label className="lbl">모델</label>
              <input className="inp" style={{ width: "100%", marginBottom: 8 }} value={model} onChange={(e) => setModel(e.target.value)} placeholder={provider === "anthropic" ? "claude-sonnet-4-5" : "gpt-4o-mini / llama3.1 등"} />
              <label className="lbl">API 키 {cfg?.ai.has_key ? "(저장됨 — 비우면 기존 키 유지)" : ""}</label>
              <input className="inp" type="password" style={{ width: "100%" }} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." />
            </div>
          )}
          {aiText && (
            <pre className="report" data-testid="ai-response">
              {aiText}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
