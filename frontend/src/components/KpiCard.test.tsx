import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiCard } from "./KpiCard";

describe("KpiCard", () => {
  it("renders an integer value with its label", () => {
    render(<KpiCard label="Orders" value={1234} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("Orders")).toBeInTheDocument();
  });

  it("renders a dash for a null value", () => {
    render(<KpiCard label="Revenue" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("prefixes currency units and rounds fractional values", () => {
    render(<KpiCard label="Revenue" value={1999.5} unit="$" />);
    expect(screen.getByText("$1,999.5")).toBeInTheDocument();
  });

  it("appends a percent unit with no space", () => {
    render(<KpiCard label="Conversion" value={42} unit="%" />);
    expect(screen.getByText("42%")).toBeInTheDocument();
  });

  it("appends a word unit with a space", () => {
    render(<KpiCard label="Users" value={88} unit="active" />);
    expect(screen.getByText("88 active")).toBeInTheDocument();
  });
});
