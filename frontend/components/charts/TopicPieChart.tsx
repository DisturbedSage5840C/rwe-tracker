"use client";

import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TopicDistributionPoint } from "@/lib/api";

const colors = ["#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#eab308"];

export function TopicPieChart({ data, isLoading }: { data: TopicDistributionPoint[]; isLoading: boolean }) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const minVisibleSlicePercent = 6;
  const chartData: TopicDistributionPoint[] = [];
  let other = 0;

  for (const item of sorted) {
    if (item.value >= minVisibleSlicePercent) {
      chartData.push(item);
    } else {
      other += item.value;
    }
  }

  if (other > 0) {
    chartData.push({ name: "other", value: Number(other.toFixed(2)) });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Topic Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[320px] w-full" />
        ) : chartData.length === 0 ? (
          <p className="text-[13px] text-slate-500">No topic clusters available.</p>
        ) : (
          <div aria-describedby="topic-pie-summary" className="h-[320px] w-full" role="img">
            <p id="topic-pie-summary" className="mb-3 text-[12px] text-slate-500">
              Distribution of real-world topics by frequency share.
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  labelLine={false}
                  label={({ name, percent }) => ((percent ?? 0) >= 0.08 ? `${name} ${((percent ?? 0) * 100).toFixed(0)}%` : "")}
                >
                  {chartData.map((entry, idx) => (
                    <Cell key={`${entry.name}-${idx}`} fill={colors[idx % colors.length]} />
                  ))}
                </Pie>
                <RechartsTooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
                <Legend verticalAlign="bottom" height={48} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
