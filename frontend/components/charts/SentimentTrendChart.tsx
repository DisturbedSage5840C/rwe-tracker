"use client";

import { format } from "date-fns";
import { Area, Bar, ComposedChart, CartesianGrid, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Line, Legend } from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TrendPoint } from "@/lib/api";

export interface SentimentTrendProps {
  data: TrendPoint[];
  onRangeChange: (days: number) => void;
  isLoading?: boolean;
  error?: string;
}

type ChartPoint = {
  date: string;
  sentiment: number;
  p25: number;
  p75: number;
  reviews: number;
};

const ranges = [
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
  { label: "180d", value: 180 },
  { label: "1y", value: 365 },
];

export function SentimentTrendChart({ data, onRangeChange, isLoading = false, error }: SentimentTrendProps) {
  const points: ChartPoint[] = data.map((point) => ({
    date: format(new Date(point.date), "MMM dd"),
    sentiment: point.perception_score,
    p25: Math.max(0, point.perception_score - 0.12),
    p75: Math.min(1, point.perception_score + 0.12),
    reviews: Math.max(0, Math.round((1 - point.gap_score) * 120)),
  }));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Sentiment Trend</CardTitle>
        <div className="flex gap-2">
          {ranges.map((range) => (
            <Button key={range.value} aria-label={`Set trend range ${range.label}`} variant="outline" size="sm" onClick={() => onRangeChange(range.value)}>
              {range.label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[360px] w-full" />
        ) : error ? (
          <p className="text-[13px] text-red-500">{error}</p>
        ) : points.length === 0 ? (
          <p className="text-[13px] text-slate-500">No trend data available yet.</p>
        ) : (
          <div aria-describedby="sentiment-trend-summary" className="h-[360px] w-full" role="img">
            <p id="sentiment-trend-summary" className="mb-3 text-[12px] text-slate-500">
              Trend line for sentiment with confidence band and review count bars.
            </p>
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="sentiment" domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={(value) => (value === 0 ? "Negative" : value === 0.5 ? "Neutral" : "Positive")} />
                <YAxis yAxisId="reviews" orientation="right" allowDecimals={false} />
                <RechartsTooltip
                  formatter={(value: number, name: string) => {
                    if (name === "Reviews") {
                      return [value.toFixed(0), name];
                    }
                    return [value.toFixed(2), name];
                  }}
                />
                <Legend />
                <Area yAxisId="sentiment" type="monotone" dataKey="p75" stroke="none" fill="#3b82f6" fillOpacity={0.1} name="P75" />
                <Area yAxisId="sentiment" type="monotone" dataKey="p25" stroke="none" fill="#ffffff" fillOpacity={1} name="P25" />
                <Bar yAxisId="reviews" dataKey="reviews" fill="#94a3b8" name="Reviews" barSize={14} />
                <Line
                  yAxisId="sentiment"
                  type="monotone"
                  dataKey="sentiment"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{
                    r: 5,
                  }}
                  name="Sentiment"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
