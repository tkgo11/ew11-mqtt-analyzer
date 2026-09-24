import type { ByteStatDto, ChecksumDto } from "../types";
import { ROLE_META, byteCellStyle, roleMeta } from "../util";

export function ByteMap({ bytes, checksum }: { bytes: ByteStatDto[]; checksum: ChecksumDto | null }) {
  return (
    <div>
      <div className="bytemap" data-testid="bytemap">
        {bytes.map((b) => (
          <div
            key={b.idx}
            className="byte-cell"
            style={byteCellStyle(b)}
            title={`[${b.idx}] ${roleMeta(b.role).ko} — 고유값 ${b.distinct}, 엔트로피 ${b.entropy.toFixed(2)}\n상위: ${b.top
              .map(([v, c]) => `${v}x${c}`)
              .join(", ")}`}
          >
            <span className="bi">[{b.idx}]</span>
            <span className="br">{roleMeta(b.role).ko}</span>
          </div>
        ))}
      </div>
      <div className="legend">
        {Object.entries(ROLE_META).map(([k, m]) => (
          <span key={k}>
            <i style={{ background: m.color }} />
            {m.ko}
          </span>
        ))}
      </div>
      {checksum && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          체크섬:{" "}
          <code className="mono">
            {checksum.algo}@{checksum.pos}
          </code>{" "}
          <span className="dim">
            커버 [{checksum.covered[0]},{checksum.covered[1]}) · 일치율 {Math.round(checksum.rate * 100)}%
            {checksum.endian ? ` · ${checksum.endian}` : ""}
          </span>
        </div>
      )}
    </div>
  );
}
