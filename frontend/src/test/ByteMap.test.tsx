import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ByteMap } from "../components/ByteMap";
import type { ByteStatDto } from "../types";

const bytes: ByteStatDto[] = [
  { idx: 0, distinct: 1, entropy: 0, top: [["F7", 10]], role: "header", const: 0xf7, is_counter: false },
  { idx: 1, distinct: 4, entropy: 2, top: [["08", 5]], role: "state", const: null, is_counter: false },
  { idx: 2, distinct: 30, entropy: 4.9, top: [["00", 3]], role: "checksum", const: null, is_counter: false },
];

describe("ByteMap", () => {
  it("renders one cell per byte with role labels", () => {
    render(<ByteMap bytes={bytes} checksum={null} />);
    const cells = screen.getByTestId("bytemap").children;
    expect(cells).toHaveLength(3);
    expect(cells[0].textContent).toContain("헤더");
    expect(cells[1].textContent).toContain("상태");
    expect(cells[2].textContent).toContain("체크섬");
  });

  it("shows checksum summary when provided", () => {
    render(
      <ByteMap
        bytes={bytes}
        checksum={{ algo: "xor", pos: 2, size: 1, covered: [1, 2], rate: 1, verified: true, endian: "" }}
      />
    );
    expect(screen.getByText(/xor@2/)).toBeTruthy();
  });
});
