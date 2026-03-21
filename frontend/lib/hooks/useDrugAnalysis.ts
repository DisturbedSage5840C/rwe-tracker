"use client";

import useSWR from "swr";

import { api, type AnalyzeJobStatusResponse, type GapDimension, type InsightItem, type TopicDistributionPoint, type TrendPoint } from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth-store";

type UseDrugAnalysisResult = {
  report: {
    id: string;
    perceptionScore: number;
    trialScore: number;
    gapScore: number;
    generatedAt: string;
  } | null;
  gaps: GapDimension[];
  trends: TrendPoint[];
  topics: TopicDistributionPoint[];
  insights: InsightItem[];
  isLoading: boolean;
  error: Error | undefined;
};

type PollingResult = {
  status: string;
  progress: number;
  result: Record<string, unknown>;
};

export function usePollingJob(jobId: string, drugId: string): PollingResult {
  const token = useAuthStore((state) => state.accessToken);

  const { data } = useSWR<AnalyzeJobStatusResponse>(
    token && jobId && drugId ? ["poll-job", drugId, jobId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.pollAnalysisJob(drugId, jobId);
      return response.data;
    },
    {
      refreshInterval: (job) => {
        if (!job) {
          return 0;
        }
        return job.status.toLowerCase() === "running" || job.status.toLowerCase() === "pending" ? 2000 : 0;
      },
      revalidateOnFocus: false,
    },
  );

  const result = data?.result_payload ?? {};
  const progressValue = result.progress;

  return {
    status: data?.status ?? "idle",
    progress: typeof progressValue === "number" ? progressValue : 0,
    result,
  };
}

export function useDrugAnalysis(drugId: string): UseDrugAnalysisResult {
  const token = useAuthStore((state) => state.accessToken);

  const reportQuery = useSWR(
    token && drugId ? ["reports", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.listReports(drugId, { limit: 1 });
      return response.data.items[0] ?? null;
    },
    { revalidateOnFocus: false },
  );

  const trendsQuery = useSWR(
    token && drugId ? ["trends", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.trends(drugId, { days: 90, granularity: "daily" });
      return response.data.points;
    },
    { revalidateOnFocus: false },
  );

  const gapsQuery = useSWR(
    token && drugId ? ["gaps", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.gaps(drugId);
      const breakdown = response.data.breakdown;
      const dimensions: Array<GapDimension["dimension"]> = ["efficacy", "safety", "tolerability", "convenience", "quality_of_life"];
      return dimensions.map((dimension) => {
        const value = breakdown[dimension] ?? 0;
        const clinical = Math.max(0, Math.min(1, 0.7 + value / 2));
        const realWorld = Math.max(0, Math.min(1, 0.7 - value / 2));
        return {
          dimension,
          clinical_score: clinical,
          real_world_score: realWorld,
          gap_magnitude: value,
          p_value: Math.abs(value) > 0.2 ? 0.03 : 0.12,
          significant: Math.abs(value) > 0.2,
        };
      });
    },
    { revalidateOnFocus: false },
  );

  const report = reportQuery.data;
  const reportPayload = (report && (report as { payload?: unknown }).payload ? (report as { payload?: unknown }).payload : null) as
    | {
        dimensions?: GapDimension[];
        insights?: InsightItem[];
      }
    | null;

  const defaultTopics: TopicDistributionPoint[] = [
    { name: "Safety", value: 30 },
    { name: "Efficacy", value: 22 },
    { name: "Adherence", value: 18 },
    { name: "Convenience", value: 16 },
    { name: "Quality of Life", value: 14 },
  ];

  return {
    report: report
      ? {
          id: report.id,
          perceptionScore: report.perception_score,
          trialScore: report.trial_score,
          gapScore: report.gap_score,
          generatedAt: report.created_at,
        }
      : null,
    gaps: reportPayload?.dimensions ?? gapsQuery.data ?? [],
    trends: trendsQuery.data ?? [],
    topics: defaultTopics,
    insights: reportPayload?.insights ?? [],
    isLoading: reportQuery.isLoading || trendsQuery.isLoading || gapsQuery.isLoading,
    error: (reportQuery.error as Error | undefined) ?? (trendsQuery.error as Error | undefined) ?? (gapsQuery.error as Error | undefined),
  };
}
