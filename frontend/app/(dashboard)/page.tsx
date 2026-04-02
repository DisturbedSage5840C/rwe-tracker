"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
  const router = useRouter();
  const token = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const setActiveDrug = useAuthStore((state) => state.setActiveDrug);
  const [selectedDrug, setSelectedDrug] = useState<DrugRead | null>(null);
  const [jobId, setJobId] = useState("");
  const [rangeDays, setRangeDays] = useState(90);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isSyncingReport, setIsSyncingReport] = useState(false);
  const [syncAttempts, setSyncAttempts] = useState(0);
  const selectedDrugId = selectedDrug?.id ?? "";

  const { status, progress } = usePollingJob(jobId, selectedDrug?.id ?? "");
  const analysis = useDrugAnalysis(selectedDrug?.id ?? "");
  const { report, refresh } = analysis;
  const normalizedStatus = status.toLowerCase();
  const isJobInFlight = Boolean(jobId) && (normalizedStatus === "pending" || normalizedStatus === "running");
  const systemStatus = useSWR(
    "/api/system",
    async () => {
      const response = await fetch("/api/system", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Unable to read service status");
      }
      return (await response.json()) as {
        frontend: { ok: boolean; detail: string };
        api: { ok: boolean; detail: string };
        nlp: { ok: boolean; detail: string };
        overall: string;
      };
    },
    { refreshInterval: 15000, revalidateOnFocus: true },
  );

  const trendsRangeQuery = useSWR(
    token && selectedDrugId ? ["trend-range", selectedDrugId, rangeDays, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.trends(selectedDrugId, { days: rangeDays, granularity: "daily" });
      return response.data.points;
    },
    { revalidateOnFocus: false },
  );

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    if (!token) {
      toast.error("Sign in required to access the dashboard");
      router.replace("/login");
    }
  }, [hydrated, token, router]);

  const onAnalyze = async () => {
    if (!token) {
      toast.error("Sign in required before starting analysis");
      router.replace("/login");
      return;
    }
    if (!selectedDrug) {
      toast.error("Select a drug before starting analysis");
      return;
    }
    if (isJobInFlight) {
      toast.message("Analysis already in progress for this drug");
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

  useEffect(() => {
    if (!jobId) {
      return;
    }
    if (normalizedStatus !== "success" && normalizedStatus !== "completed") {
      return;
    }
    if (report) {
      setIsSyncingReport(false);
      setSyncAttempts(0);
      return;
    }
    if (isSyncingReport) {
      return;
    }

    let cancelled = false;
    const syncReport = async () => {
      setIsSyncingReport(true);
      const maxAttempts = 8;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        if (cancelled) {
          return;
        }
        setSyncAttempts(attempt);
        const refreshed = await refresh();
        if (refreshed.report) {
          setIsSyncingReport(false);
          setSyncAttempts(0);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      if (!cancelled) {
        setIsSyncingReport(false);
      }
    };

    void syncReport();

    return () => {
      cancelled = true;
    };
  }, [isSyncingReport, jobId, normalizedStatus, refresh, report]);

  const isTerminalJob = normalizedStatus === "success" || normalizedStatus === "completed";
  const shouldShowResults = Boolean(selectedDrug && analysis.report);
  const shouldShowNoDataMessage = Boolean(selectedDrug && isTerminalJob && !analysis.report && !isSyncingReport);
  const shouldShowSyncCard = Boolean(selectedDrug && isSyncingReport && !analysis.report);
  const hasRealWorldSamples = Boolean((analysis.report?.sampleSizeReviews ?? 0) + (analysis.report?.sampleSizeSocial ?? 0) > 0);
  const hasMeaningfulVisualData = analysis.trends.length > 0 || analysis.insights.length > 0;
  const hasDerivedVisualData = analysis.gaps.length > 0 || hasMeaningfulVisualData;
  const hasZeroedScores =
    Boolean(analysis.report) &&
    Math.abs(analysis.report?.perceptionScore ?? 0) < 0.000001 &&
    Math.abs(analysis.report?.trialScore ?? 0) < 0.000001 &&
    Math.abs(analysis.report?.gapScore ?? 0) < 0.000001;
  const shouldShowInsufficientDataState = Boolean(selectedDrug && analysis.report && !hasRealWorldSamples && !hasMeaningfulVisualData);
  const shouldShowZeroedDataState = Boolean(selectedDrug && hasZeroedScores && !hasDerivedVisualData);

  if (!hydrated || !token) {
    return (
      <DashboardErrorBoundary>
        <main className="min-h-screen bg-slate-50 px-8 py-8">
          <div className="mx-auto max-w-[1400px] rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
            Preparing secure dashboard session...
          </div>
        </main>
      </DashboardErrorBoundary>
    );
  }

  return (
    <DashboardErrorBoundary>
      <main className="min-h-screen bg-slate-50 px-8 py-8">
        <div className="mx-auto max-w-[1400px] space-y-6">
          <header className="space-y-2">
            <h1 className="text-2xl font-semibold text-slate-900">RWE Perception Dashboard</h1>
            <p className="text-[13px] text-slate-600">Monitor gaps between clinical claims and real-world patient outcomes.</p>
            <div className="flex flex-wrap gap-2 pt-1 text-[12px]">
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-700">Frontend: connected</span>
              <span
                className={`rounded-full border px-3 py-1 ${
                  systemStatus.data?.api.ok
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                API: {systemStatus.data?.api.ok ? "connected" : systemStatus.data?.api.detail ?? "checking"}
              </span>
              <span
                className={`rounded-full border px-3 py-1 ${
                  systemStatus.data?.nlp.ok
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                NLP: {systemStatus.data?.nlp.ok ? "connected" : systemStatus.data?.nlp.detail ?? "checking"}
              </span>
            </div>
          </header>

          <Card>
            <CardContent className="flex items-center justify-between gap-4 p-6">
              <DrugSearchCombobox
                value={selectedDrug?.name ?? ""}
                onChange={(drug) => {
                  setSelectedDrug(drug);
                  setActiveDrug(drug.id);
                  setJobId("");
                  setIsSyncingReport(false);
                  setSyncAttempts(0);
                }}
              />
              <Button aria-label="Analyze selected drug" disabled={!selectedDrug || isTriggering || isJobInFlight} onClick={onAnalyze}>
                {isTriggering ? "Starting..." : isJobInFlight ? "Running..." : "Analyze"}
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
          ) : shouldShowSyncCard ? (
            <Card>
              <CardContent className="space-y-2 p-6 text-[13px] text-slate-600">
                <p>Analysis finished. Loading the generated report...</p>
                <p className="text-slate-500">Sync attempt {syncAttempts}/8</p>
              </CardContent>
            </Card>
          ) : shouldShowNoDataMessage ? (
            <Card>
              <CardContent className="space-y-3 p-6 text-[13px] text-slate-600">
                <p>Analysis completed but no report data is available yet for this drug.</p>
                <Button
                  variant="secondary"
                  onClick={() => {
                    void analysis.refresh();
                  }}
                >
                  Refresh data
                </Button>
              </CardContent>
            </Card>
          ) : shouldShowInsufficientDataState ? (
            <Card>
              <CardContent className="space-y-2 p-6 text-[13px] text-slate-600">
                <p>Analysis completed, but there is not enough real-world evidence for this run yet.</p>
                <p className="text-slate-500">
                  Extracted counts for this record: reviews {analysis.report?.sourceMetrics?.counts?.reviews ?? analysis.report?.sampleSizeReviews ?? 0}, social mentions {analysis.report?.sourceMetrics?.counts?.social_mentions ?? analysis.report?.sampleSizeSocial ?? 0}, clinical trials {analysis.report?.sourceMetrics?.counts?.clinical_trials ?? 0}.
                </p>
                <p className="text-slate-500">Try running analysis on a different drug record entry with populated sources, or re-run after source credentials/network are fixed.</p>
              </CardContent>
            </Card>
          ) : shouldShowZeroedDataState ? (
            <Card>
              <CardContent className="space-y-2 p-6 text-[13px] text-slate-600">
                <p>Analysis completed, but the generated report contains zeroed metrics and no supporting trend/insight data.</p>
                <p className="text-slate-500">Please run Analyze again for this drug entry or choose a different entry in the list.</p>
              </CardContent>
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
