"use client";

import { useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";

import { GapRadarChart } from "@/components/charts/GapRadarChart";
import { SentimentTrendChart } from "@/components/charts/SentimentTrendChart";
import { TopicPieChart } from "@/components/charts/TopicPieChart";
import { DrugOverviewCard } from "@/components/drug/DrugOverviewCard";
import { DrugSearchCombobox } from "@/components/drug/DrugSearchCombobox";
import { DashboardErrorBoundary } from "@/components/errors/DashboardErrorBoundary";
import { InsightsList } from "@/components/insights/InsightsList";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DrugRead } from "@/lib/api";
import { useDrugAnalysis, usePollingJob } from "@/lib/hooks/useDrugAnalysis";
import { useAuthStore } from "@/lib/store/auth-store";

export default function DashboardPage() {
  const token = useAuthStore((state) => state.accessToken);
  const setActiveDrug = useAuthStore((state) => state.setActiveDrug);
  const [selectedDrug, setSelectedDrug] = useState<DrugRead | null>(null);
  const [jobId, setJobId] = useState("");
  const [rangeDays, setRangeDays] = useState(90);
  const [isTriggering, setIsTriggering] = useState(false);
  const selectedDrugId = selectedDrug?.id ?? "";

  const { status, progress } = usePollingJob(jobId, selectedDrug?.id ?? "");
  const analysis = useDrugAnalysis(selectedDrug?.id ?? "");

  const trendsRangeQuery = useSWR(
    token && selectedDrugId ? ["trend-range", selectedDrugId, rangeDays, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.trends(selectedDrugId, { days: rangeDays, granularity: "daily" });
      return response.data.points;
    },
    { revalidateOnFocus: false },
  );

  const onAnalyze = async () => {
    if (!selectedDrug || !token) {
      toast.error("Select a drug before starting analysis");
      return;
    }
    setIsTriggering(true);
    try {
      api.setAccessToken(token);
      const trigger = await api.triggerAnalysis(selectedDrug.id);
      setJobId(trigger.data.job_id);
      toast.success("Analysis job started");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to trigger analysis");
    } finally {
      setIsTriggering(false);
    }
  };

  const shouldShowResults = Boolean(selectedDrug && (analysis.report || status === "SUCCESS" || status === "completed"));

  return (
    <DashboardErrorBoundary>
      <main className="min-h-screen bg-slate-50 px-8 py-8">
        <div className="mx-auto max-w-[1400px] space-y-6">
          <header className="space-y-2">
            <h1 className="text-2xl font-semibold text-slate-900">RWE Perception Dashboard</h1>
            <p className="text-[13px] text-slate-600">Monitor gaps between clinical claims and real-world patient outcomes.</p>
          </header>

          <Card>
            <CardContent className="flex items-center justify-between gap-4 p-6">
              <DrugSearchCombobox
                value={selectedDrug?.name ?? ""}
                onChange={(drug) => {
                  setSelectedDrug(drug);
                  setActiveDrug(drug.id);
                  setJobId("");
                }}
              />
              <Button aria-label="Analyze selected drug" disabled={!selectedDrug || isTriggering} onClick={onAnalyze}>
                {isTriggering ? "Starting..." : "Analyze"}
              </Button>
            </CardContent>
          </Card>

          {jobId ? (
            <Card>
              <CardContent className="space-y-2 p-6">
                <div className="flex items-center justify-between text-[13px] text-slate-600">
                  <span>Job status: {status}</span>
                  <span>{progress.toFixed(2)}%</span>
                </div>
                <Progress aria-label="Analysis progress" value={progress} />
              </CardContent>
            </Card>
          ) : null}

          {!selectedDrug ? (
            <Card>
              <CardContent className="p-6 text-[13px] text-slate-600">Search and select a drug to begin analysis.</CardContent>
            </Card>
          ) : !shouldShowResults ? (
            <div className="grid gap-4">
              <Skeleton className="h-[180px] w-full" />
              <Skeleton className="h-[400px] w-full" />
              <Skeleton className="h-[360px] w-full" />
            </div>
          ) : (
            <div className="space-y-4">
              <DrugOverviewCard
                perceptionScore={analysis.report?.perceptionScore ?? 0}
                trialScore={analysis.report?.trialScore ?? 0}
                gapScore={analysis.report?.gapScore ?? 0}
                isLoading={analysis.isLoading}
              />
              <div className="grid grid-cols-2 gap-4">
                <GapRadarChart gaps={analysis.gaps} isLoading={analysis.isLoading} />
                <TopicPieChart data={analysis.topics} isLoading={analysis.isLoading} />
              </div>
              <SentimentTrendChart
                data={trendsRangeQuery.data ?? analysis.trends}
                onRangeChange={(days) => setRangeDays(days)}
                isLoading={analysis.isLoading || trendsRangeQuery.isLoading}
                error={analysis.error?.message}
              />
              <InsightsList insights={analysis.insights} isLoading={analysis.isLoading} sendPrompt={(prompt) => toast.message(`Ask AI: ${prompt}`)} />
            </div>
          )}
        </div>
      </main>
    </DashboardErrorBoundary>
  );
}
