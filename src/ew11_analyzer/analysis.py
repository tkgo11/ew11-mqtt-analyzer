"""Full-analysis orchestrator: families -> verdicts, bytemaps, checksums, diffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bytemap import byte_map
from .checksums import detect_checksum
from .classify import Marker, classify_family
from .diffing import MarkerDiff, diff_around_markers
from .families import group_families
from .packets import Packet

MAX_FAMILIES = 60
MAX_SAMPLES_PER_FAMILY = 8


@dataclass
class FamilyReport:
    sig: str
    verdict: dict[str, Any]  # FamilyVerdict.to_dict()
    bytemap: list[dict[str, Any]]  # ByteStat.to_dict()
    checksum: dict[str, Any] | None  # best ChecksumMatch.to_dict()
    checksum_candidates: list[dict[str, Any]]
    samples: list[str]  # hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "sig": self.sig,
            "verdict": self.verdict,
            "bytemap": self.bytemap,
            "checksum": self.checksum,
            "checksum_candidates": self.checksum_candidates,
            "samples": self.samples,
        }


@dataclass
class AnalysisResult:
    started_at: float
    ended_at: float
    total_packets: int
    total_families: int
    markers: list[dict[str, Any]]
    families: list[FamilyReport] = field(default_factory=list)
    diffs: list[MarkerDiff] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": round(max(self.ended_at - self.started_at, 0.0), 2),
            "total_packets": self.total_packets,
            "total_families": self.total_families,
            "markers": self.markers,
            "families": [f.to_dict() for f in self.families],
            "diffs": [d.to_dict() for d in self.diffs],
            "notes": self.notes,
            "params": self.params,
        }


def run_analysis(
    packets: list[Packet],
    markers: list[Marker],
    prefix_len: int = 3,
    *,
    pre: float = 0.3,
    post: float = 1.5,
    max_families: int = MAX_FAMILIES,
) -> AnalysisResult:
    start = min((p.ts for p in packets), default=0.0)
    end = max((p.ts for p in packets), default=0.0)
    fams = group_families(packets, prefix_len)
    # analyze the busiest families first; cap to keep the report usable
    top = sorted(fams.items(), key=lambda kv: -len(kv[1]))[:max_families]

    result = AnalysisResult(
        started_at=start,
        ended_at=end,
        total_packets=len(packets),
        total_families=len(fams),
        markers=[{"id": m.id, "ts": m.ts, "label": m.label} for m in markers],
        params={"prefix_len": prefix_len, "event_pre": pre, "event_post": post},
    )

    for sig, pkts in top:
        verdict = classify_family(
            sig,
            [p.ts for p in pkts],
            [p.topic for p in pkts],
            markers=markers,
            start=start,
            end=end,
            pre=pre,
            post=post,
        )
        samples = [p.payload for p in pkts]
        chk_matches = detect_checksum(samples)
        chk_positions: set[int] = set()
        if chk_matches:
            best = chk_matches[0]
            chk_positions = set(range(best.pos, min(best.pos + best.size, len(samples[0]))))
        bm = byte_map(samples, checksum_positions=chk_positions, prefix_len=prefix_len)
        result.families.append(
            FamilyReport(
                sig=sig,
                verdict=verdict.to_dict(),
                bytemap=[b.to_dict() for b in bm],
                checksum=chk_matches[0].to_dict() if chk_matches else None,
                checksum_candidates=[c.to_dict() for c in chk_matches],
                samples=[p.hex for p in pkts[:MAX_SAMPLES_PER_FAMILY]],
            )
        )

    if markers:
        result.diffs = diff_around_markers(packets, markers, pre=pre, post=post, prefix_len=prefix_len)

    # guidance notes (Korean; the UI is Korean-first)
    if not markers:
        result.notes.append(
            "이벤트 마커가 없습니다. 월패드 버튼을 누르는 순간 '이벤트 표시'를 눌러 주면 "
            "어떤 패킷이 명령인지 자동으로 구분됩니다."
        )
    if len(packets) < 20:
        result.notes.append("수집된 패킷이 매우 적습니다. 잠시 더 수집한 뒤 분석하세요.")
    if len(fams) > max_families:
        result.notes.append(
            f"패밀리가 {len(fams)}개라 상위 {max_families}개만 분석했습니다. "
            "토픽 필터로 범위를 좁히면 더 정확합니다."
        )
    if any(f.verdict["event_count"] > 0 and f.verdict["event_lift"] is None for f in result.families):
        result.notes.append(
            "이벤트 구간과 평상시 구간의 수집 시간이 부족해 빈도를 비교할 수 없습니다. "
            "버튼을 누르지 않은 상태에서 더 수집하거나 이벤트 윈도우를 줄여 보세요."
        )
    elif not any(f.verdict["verdict"] == "EVENT" for f in result.families) and markers:
        result.notes.append(
            "이벤트로 분류된 패밀리가 없습니다. 마커 시각과 패킷 도착 시각의 오차를 줄이려면 "
            "버튼을 누르는 순간과 동시에 표시하거나, 설정의 이벤트 윈도우를 늘려 보세요."
        )
    return result
