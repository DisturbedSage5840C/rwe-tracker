"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Tooltip as RechartsTooltip, Legend } from "recharts";

import type { GapDimension } from "@/lib/api";

export interface GapRadarChartProps {
  gaps: GapDimension[];
  isLoading: boolean;
}

type RadarPoint = {
  axis: string;
  clinical: number;
  realWorld: number;
  gapMagnitude: number;
  significant: boolean;
  pValue: number;
  underfill: number;
  overfill: number;
};

const axisLabels: Record<GapDimension["dimension"], string> = {
  efficacy: "Efficacy",
  safety: "Safety",
  tolerability: "Tolerability",
  convenience: "Convenience",
  quality_of_life: "Quality of Life",
  adherence: "Adherence",
  trust: "Trust",
};

function normalize(value: number): number {
  return Math.max(0, Math.min(1, value));
}

export function GapRadarChart({ gaps, isLoading }: GapRadarChartProps) {
  const hasData = gaps.length > 0;

  const points: RadarPoint[] = gaps.map((gap) => ({
    axis: axisLabels[gap.dimension],
    clinical: normalize(gap.clinical_score),
    realWorld: normalize(gap.real_world_score),
    gapMagnitude: gap.gap_magnitude,
    significant: gap.significant,
    pValue: gap.p_value,
    underfill: gap.real_world_score < gap.clinical_score ? normalize(gap.clinical_score) : 0,
    overfill: gap.real_world_score > gap.clinical_score ? normalize(gap.real_world_score) : 0,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Gap Radar</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[400px] w-full" />
        ) : !hasData ? (
          <p className="text-[13px] text-slate-500">No gap dimensions available for this drug yet.</p>
        ) : (
          <div aria-describedby="gap-radar-summary" className="h-[400px] w-full" role="img">
            <p id="gap-radar-summary" className="mb-3 text-[12px] text-slate-500">
              Radar chart comparing clinical claims and real-world sentiment across efficacy, safety, tolerability, convenience, and quality of life.
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={points}>
                <PolarGrid />
                <PolarAngleAxis dataKey="axis" />
                <PolarRadiusAxis domain={[0, 1]} tickCount={6} />
                <Radar name="Gap below claim" dataKey="underfill" stroke="none" fill="#ef4444" fillOpacity={0.15} />
                <Radar name="Gap above claim" dataKey="overfill" stroke="none" fill="#22c55e" fillOpacity={0.15} />
                <Radar name="Clinical claims" dataKey="clinical" stroke="#22c55e" fill="#22c55e" fillOpacity={0.2} />
                <Radar name="Real-world perception" dataKey="realWorld" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
                <RechartsTooltip
                  formatter={(value: number, name: string, props) => {
                    if (name === "Clinical claims") {
                      return [value.toFixed(2), "Clinical score"];
                    }
                    if (name === "Real-world perception") {
                      return [value.toFixed(2), "Real-world score"];
                    }
                    if (props.payload) {
                      return [
                        `${props.payload.gapMagnitude.toFixed(2)} (${props.payload.significant ? "✓ significant" : "— not significant"})`,
                        "Gap magnitude",
                      ];
                    }
                    return [value.toFixed(2), name];
                  }}
                  labelFormatter={(label, payload) => {
                    if (!payload || payload.length === 0) {
                      return label;
                    }
                    const point = payload[0].payload as RadarPoint;
                    return `${point.axis}: clinical ${point.clinical.toFixed(2)}, real-world ${point.realWorld.toFixed(2)}, p ${point.pValue < 0.05 ? "< 0.05" : `= ${point.pValue.toFixed(2)}`}`;
                  }}
                />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
