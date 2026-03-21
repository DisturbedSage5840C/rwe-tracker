"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InsightAlert } from "@/components/insights/InsightAlert";
import type { InsightItem } from "@/lib/api";

export function InsightsList({
  insights,
  isLoading,
  sendPrompt,
}: {
  insights: InsightItem[];
  isLoading: boolean;
  sendPrompt: (prompt: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Insights</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <>
            <Skeleton className="h-[96px] w-full" />
            <Skeleton className="h-[96px] w-full" />
          </>
        ) : insights.length === 0 ? (
          <p className="text-[13px] text-slate-500">No insight records are available yet for this analysis.</p>
        ) : (
          insights.map((insight, index) => <InsightAlert key={`${insight.dimension}-${index}`} insight={insight} sendPrompt={sendPrompt} />)
        )}
      </CardContent>
    </Card>
  );
}
