"use client";

import { ChevronDown, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { InsightItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const severityStyles: Record<InsightItem["severity"], string> = {
  critical: "border-l-red-500",
  high: "border-l-orange-500",
  moderate: "border-l-yellow-500",
};

export function InsightAlert({ insight, sendPrompt }: { insight: InsightItem; sendPrompt: (prompt: string) => void }) {
  const question = `Explain why ${insight.dimension.replaceAll("_", " ")} has ${insight.severity} severity and suggest next medical-affairs action for this drug.`;

  return (
    <Collapsible className={cn("rounded-lg border border-slate-200 border-l-4 bg-white p-4", severityStyles[insight.severity])}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{insight.dimension.replaceAll("_", " ")}</Badge>
            <Badge variant={insight.severity === "critical" ? "destructive" : insight.severity === "high" ? "warning" : "secondary"}>{insight.severity}</Badge>
            <Badge variant="outline">{insight.p_value < 0.05 ? "p < 0.05" : `p = ${insight.p_value.toFixed(2)}`}</Badge>
          </div>
          <p className="text-sm text-slate-900">{insight.message}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button aria-label="Ask AI about this insight" variant="outline" size="sm" onClick={() => sendPrompt(question)}>
            <Sparkles className="mr-1 h-4 w-4" /> Ask AI
          </Button>
          <CollapsibleTrigger asChild>
            <Button aria-label="Expand recommendation" variant="ghost" size="icon">
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
        </div>
      </div>
      <CollapsibleContent className="pt-3 text-[13px] text-slate-600">{insight.recommendation}</CollapsibleContent>
    </Collapsible>
  );
}
