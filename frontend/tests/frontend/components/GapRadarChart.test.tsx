import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { GapRadarChart } from "@/components/charts/GapRadarChart";
import type { GapDimension } from "@/lib/api";

vi.mock("recharts", () => {
  return {
    ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    RadarChart: ({ data, children }: { data: Array<{ axis: string; clinical: number; realWorld: number; gapMagnitude: number; significant: boolean }>; children: ReactNode }) => (
      <div>
        {data.map((point) => (
          <button
            key={point.axis}
            type="button"
            aria-label={`point-${point.axis}`}
            onMouseOver={(event) => {
              const target = event.currentTarget;
              target.setAttribute(
                "data-tooltip",
                `${point.axis}: clinical ${point.clinical.toFixed(2)}, real-world ${point.realWorld.toFixed(2)}, gap ${point.gapMagnitude.toFixed(2)} (${point.significant ? "✓ significant" : "— not significant"})`,
              );
            }}
          >
            {point.axis}
          </button>
        ))}
        {children}
      </div>
    ),
    PolarGrid: () => null,
    PolarAngleAxis: () => null,
    PolarRadiusAxis: () => null,
    Radar: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

const gaps: GapDimension[] = [
  {
    dimension: "efficacy",
    clinical_score: 0.8,
    real_world_score: 0.6,
    gap_magnitude: -0.2,
    p_value: 0.03,
    significant: true,
  },
  {
    dimension: "safety",
    clinical_score: 0.7,
    real_world_score: 0.8,
    gap_magnitude: 0.1,
    p_value: 0.12,
    significant: false,
  },
  {
    dimension: "tolerability",
    clinical_score: 0.6,
    real_world_score: 0.4,
    gap_magnitude: -0.2,
    p_value: 0.04,
    significant: true,
  },
  {
    dimension: "convenience",
    clinical_score: 0.75,
    real_world_score: 0.7,
    gap_magnitude: -0.05,
    p_value: 0.3,
    significant: false,
  },
  {
    dimension: "quality_of_life",
    clinical_score: 0.65,
    real_world_score: 0.7,
    gap_magnitude: 0.05,
    p_value: 0.2,
    significant: false,
  },
];

describe("GapRadarChart", () => {
  it("renders loading skeleton when isLoading=true", () => {
    render(<GapRadarChart gaps={[]} isLoading />);
    expect(document.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("renders chart with correct number of data points", () => {
    render(<GapRadarChart gaps={gaps} isLoading={false} />);
    expect(screen.getAllByRole("button").length).toBe(5);
  });

  it("tooltip shows correct values on hover", () => {
    render(<GapRadarChart gaps={gaps} isLoading={false} />);

    const point = screen.getByRole("button", { name: "point-Efficacy" });
    fireEvent.mouseOver(point);
    expect(point.getAttribute("data-tooltip")).toContain("clinical 0.80");
    expect(point.getAttribute("data-tooltip")).toContain("✓ significant");
  });

  it("handles empty gaps array without crashing", () => {
    render(<GapRadarChart gaps={[]} isLoading={false} />);
    expect(screen.getByText("No gap dimensions available for this drug yet.")).toBeTruthy();
  });
});
