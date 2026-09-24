"""AI-ready report generation (Markdown / JSON / CSV).

The Markdown report is designed to be pasted directly into an LLM: it carries
a task preamble, family tables, byte maps, samples and event correlations.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from .analysis import AnalysisResult

AI_TASK_PREAMBLE = """\
# AI 분석 요청

아래 데이터는 EW11(RS485↔WiFi)을 통해 수집한 아파트 월패드 버스 트래픽을
자동 분석한 결과입니다. 다음을 도와주세요:

1. **프로토콜 구조 추정**: 각 패밀리의 헤더/주소/명령/데이터/체크섬/꼬리 바이트를 추정해 주세요.
2. **패밀리 의미 추측**: 주기 신호는 상태 브로드캐스트일 가능성이 높고, 이벤트는 명령/응답입니다.
   어떤 장치(조명/난방/환기/가스/엘리베이터 등)에 해당하는지 추측해 주세요.
3. **체크섬 검증**: 감지된 체크섬 알고리즘이 맞는지 샘플로 검증해 주세요.
4. **명령 바이트 추정**: 이벤트 패킷에서 어떤 바이트가 명령/값을 나타내는지 추정해 주세요.
5. **다음 실험 제안**: 추정을 확정하기 위해 어떤 버튼을 눌러보면 좋을지 제안해 주세요.

한국 월패드 프로토콜(코콤, 코맥스, 현대통신, 삼성SDS, EZVILLE, 대성산업 등)의
관례를 참고하되, 확실하지 않은 부분은 "추정"이라고 표시해 주세요.
"""

ROLE_KO = {
    "header": "헤더",
    "const": "고정",
    "tail": "꼬리(ETX)",
    "checksum": "체크섬",
    "counter": "카운터",
    "state": "상태",
    "data": "데이터",
}


def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "-"


def _overview_lines(d: dict[str, Any]) -> list[str]:
    lines = ["# 수집 개요", ""]
    lines.append(f"- 수집 시작: {_ts(d['started_at'])}")
    lines.append(f"- 수집 종료: {_ts(d['ended_at'])} (총 {d['duration_s']}초)")
    lines.append(f"- 총 패킷: {d['total_packets']}개 / 패밀리 {d['total_families']}개")
    lines.append(
        f"- 분석 파라미터: prefix={d['params'].get('prefix_len')}B, "
        f"이벤트 윈도우={d['params'].get('event_pre')}s ~ +{d['params'].get('event_post')}s"
    )
    if d["notes"]:
        lines.append("- 참고: " + " / ".join(d["notes"]))
    return lines


def _markers_lines(d: dict[str, Any]) -> list[str]:
    lines = ["# 이벤트 마커", ""]
    if not d["markers"]:
        lines.append("(없음 — 버튼을 누를 때 이벤트를 표시하면 명령 패킷을 구분할 수 있습니다)")
        return lines
    lines += ["| ID | 시각 | 라벨 |", "|---|---|---|"]
    for m in d["markers"]:
        ms = int(m["ts"] * 1000) % 1000
        lines.append(f"| {m['id']} | {_ts(m['ts'])}.{ms:03d} | {m['label']} |")
    return lines


def _family_summary_lines(d: dict[str, Any]) -> list[str]:
    lines = ["# 패밀리 요약", ""]
    lines += ["| 시그니처 | 개수 | 분당 | 주기성 | 판정 | 신뢰도 | 체크섬 |", "|---|---|---|---|---|---|---|"]
    for f in d["families"]:
        v = f["verdict"]
        chk = f["checksum"]
        chk_s = f"{chk['algo']}@{chk['pos']} ({int(chk['rate'] * 100)}%)" if chk else "-"
        per = f"{v['periodicity'] * 100:.0f}%"
        lines.append(
            f"| `{f['sig']}` | {v['count']} | {v['rate_per_min']} | {per} | "
            f"{v['verdict_ko']}({v['verdict']}) | {v['confidence']:.2f} | {chk_s} |"
        )
    return lines


def _family_detail_lines(f: dict[str, Any]) -> list[str]:
    v = f["verdict"]
    lines = [
        f"## `{f['sig']}` — {v['verdict_ko']} (신뢰도 {v['confidence']:.2f})",
        "",
        f"- 개수 {v['count']}, 분당 {v['rate_per_min']}, 평균 간격 "
        f"{v['mean_interval'] if v['mean_interval'] is not None else '-'}s, "
        f"주기성 {v['periodicity'] * 100:.0f}%",
        f"- 기준선 {v['baseline_count']}회 / 이벤트 윈도우 내 {v['event_count']}회"
        + (f", lift={v['event_lift']}" if v["event_lift"] is not None else ""),
        f"- 토픽: {', '.join(v['topics'])}",
    ]
    if v["marker_ids"]:
        lines.append(f"- 연관 마커: {v['marker_ids']}")
    if f["checksum"]:
        c = f["checksum"]
        lines.append(
            f"- 체크섬: `{c['algo']}` pos={c['pos']} size={c['size']}B, "
            f"커버 범위 [{c['covered'][0]},{c['covered'][1]}), 일치율 {c['rate'] * 100:.0f}%"
            + (", little-endian" if c["endian"] == "little" else "")
        )
    lines += ["", "| 바이트 | 역할 | 상위 값(빈도) | 엔트로피 |", "|---|---|---|---|"]
    for b in f["bytemap"]:
        tops = ", ".join(f"{val}x{cnt}" for val, cnt in b["top"][:3])
        role = ROLE_KO.get(b["role"], b["role"])
        if b["is_counter"] and b["role"] != "counter":
            role += "+카운터"
        lines.append(f"| [{b['idx']}] | {role} | {tops} | {b['entropy']:.2f} |")
    lines += ["", "샘플:", "```"]
    lines += f["samples"]
    lines += ["```", ""]
    return lines


def _diffs_lines(d: dict[str, Any]) -> list[str]:
    lines = ["# 마커별 차이 분석", ""]
    for diff in d["diffs"]:
        m = diff["marker"]
        lines.append(f"## 마커 #{m['id']} `{m['label']}` @ {_ts(m['ts'])}")
        lines.append("")
        if not diff["hits"]:
            lines.append("윈도우 내 패킷 없음.")
        for h in diff["hits"][:8]:
            flag = " **[신규]**" if h["novel"] else ""
            chg = ",".join(f"[{p}]" for p in h["changed_positions"]) or "-"
            lines.append(f"- `{h['sig']}` x{h['count_in']}{flag} — 변경 바이트: {chg}")
            for s in h["samples_in"][:3]:
                lines.append(f"    - `{s}`")
        lines.append("")
    return lines


def to_markdown(result: AnalysisResult) -> str:
    d = result.to_dict()
    lines: list[str] = [AI_TASK_PREAMBLE, "", "---", ""]
    lines += _overview_lines(d)
    lines += ["", *_markers_lines(d)]
    lines += ["", *_family_summary_lines(d)]
    lines += ["", "# 패밀리 상세", ""]
    for f in d["families"]:
        lines += _family_detail_lines(f)
    if d["diffs"]:
        lines += ["", *_diffs_lines(d)]
    return "\n".join(lines)


def to_json(result: AnalysisResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=1)


def packets_to_csv(packets: Iterable[Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["seq", "ts", "iso_time", "topic", "len", "hex", "fmt"])
    for p in packets:
        w.writerow([p.seq, f"{p.ts:.3f}", _ts(p.ts), p.topic, p.size, p.hex, p.fmt])
    return buf.getvalue()
