import { describe, expect, it } from "vitest";
import { familySig, fmtInterval, fmtTime, hexWithDiff, roleMeta, verdictMeta } from "../util";

describe("familySig", () => {
  it("builds prefix:length signature", () => {
    expect(familySig("F7 0A 01 40 11 01 01 FF 2A EE")).toBe("F70A01:10");
  });
  it("respects prefixLen", () => {
    expect(familySig("F7 0A 01 40", 2)).toBe("F70A:4");
  });
  it("handles extra whitespace", () => {
    expect(familySig("  F7  0A 01 ")).toBe("F70A01:3");
  });
});

describe("roleMeta / verdictMeta", () => {
  it("maps known roles", () => {
    expect(roleMeta("checksum").ko).toBe("체크섬");
    expect(roleMeta("counter").ko).toBe("카운터");
  });
  it("falls back for unknown roles", () => {
    expect(roleMeta("mystery").ko).toBe("mystery");
  });
  it("maps verdicts to ko + css class", () => {
    expect(verdictMeta("EVENT").ko).toBe("이벤트");
    expect(verdictMeta("IDLE").cls).toBe("badge-idle");
    expect(verdictMeta("???").cls).toBe("badge-unknown");
  });
});

describe("hexWithDiff", () => {
  it("marks changed positions", () => {
    const cells = hexWithDiff("F7 0A 01", [1]);
    expect(cells.map((c) => c.changed)).toEqual([false, true, false]);
  });
});

describe("fmt helpers", () => {
  it("formats time with ms", () => {
    expect(fmtTime(1700000000.5)).toMatch(/\d{2}:\d{2}:\d{2}\.\d{3}/);
  });
  it("formats intervals", () => {
    expect(fmtInterval(null)).toBe("-");
    expect(fmtInterval(0.005)).toBe("5.0ms");
    expect(fmtInterval(1.5)).toBe("1.50s");
    expect(fmtInterval(90)).toBe("1.5min");
  });
});
