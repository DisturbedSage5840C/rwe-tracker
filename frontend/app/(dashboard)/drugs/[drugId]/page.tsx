"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { useVirtualizer } from "@tanstack/react-virtual";
import { format } from "date-fns";
import { toast } from "sonner";

import { GapRadarChart } from "@/components/charts/GapRadarChart";
import { SentimentTrendChart } from "@/components/charts/SentimentTrendChart";
import { TopicPieChart } from "@/components/charts/TopicPieChart";
import { DrugOverviewCard } from "@/components/drug/DrugOverviewCard";
import { InsightsList } from "@/components/insights/InsightsList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useDrugAnalysis } from "@/lib/hooks/useDrugAnalysis";
import { useAuthStore } from "@/lib/store/auth-store";

export default function DrugDetailPage() {
  const router = useRouter();
  const params = useParams<{ drugId: string }>();
  const token = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const drugId = params.drugId;

  const analysis = useDrugAnalysis(drugId);

  const drugQuery = useSWR(
    token ? ["drug-detail", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.getDrug(drugId);
      return response.data;
    },
    { revalidateOnFocus: false },
  );

  const reportsQuery = useSWR(
    token ? ["drug-reports", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.listReports(drugId, { limit: 20 });
      return response.data.items;
    },
    { revalidateOnFocus: false },
  );

  const trendsQuery = useSWR(
    token ? ["drug-trends", drugId, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.trends(drugId, { days: 180, granularity: "weekly" });
      return response.data.points;
    },
    { revalidateOnFocus: false },
  );

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    if (!token) {
      toast.error("Sign in required to access this page");
      router.replace("/login");
    }
  }, [hydrated, token, router]);

  const resolvedReport = analysis.report
    ? analysis.report
    : drugQuery.data?.latest_report
      ? {
          id: drugQuery.data.latest_report.id,
          perceptionScore: drugQuery.data.latest_report.perception_score,
          trialScore: drugQuery.data.latest_report.trial_score,
          gapScore: drugQuery.data.latest_report.gap_score,
          generatedAt: drugQuery.data.latest_report.created_at,
          sampleSizeReviews: 0,
          sampleSizeSocial: 0,
        }
      : null;

  const pageError =
    (drugQuery.error as Error | undefined) ??
    (reportsQuery.error as Error | undefined) ??
    (trendsQuery.error as Error | undefined) ??
    analysis.error;

  const reviewRows = useMemo(() => {
    const sampleSize = analysis.report ? Math.max(analysis.report.gapScore > 0 ? 250 : 80, 80) : 80;
    return Array.from({ length: Math.min(1200, sampleSize * 4) }).map((_, index) => ({
      id: `${drugId}-${index}`,
      date: new Date(Date.now() - index * 86_400_000),
      sentiment: Math.max(0, Math.min(1, 0.45 + Math.sin(index / 12) * 0.15)),
      source: index % 2 === 0 ? "Patient forum" : "Social mention",
      excerpt: `Synthetic review ${index + 1} generated for virtualization placeholder until dedicated reviews endpoint is available.`,
    }));
  }, [analysis.report, drugId]);

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: reviewRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 8,
  });

  const exportFile = async (formatType: "csv" | "pdf") => {
    if (!token) {
      return;
    }
    try {
      api.setAccessToken(token);
      const blob = formatType === "csv" ? await api.exportReportsCsv(drugId) : await api.exportReportsPdf(drugId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `drug-${drugId}-reports.${formatType}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to export report");
    }
  };

  if (!hydrated || !token) {
    return (
      <main className="min-h-screen bg-slate-50 px-8 py-8">
        <div className="mx-auto max-w-[1440px] rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
          Preparing secure session...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-8 py-8">
      <div className="mx-auto grid max-w-[1440px] grid-cols-[320px_1fr] gap-6">
        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Drug Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[13px] text-slate-700">
              <p><span className="text-slate-500">Name:</span> {drugQuery.data?.name ?? "-"}</p>
              <p><span className="text-slate-500">Indication:</span> {drugQuery.data?.indication ?? "-"}</p>
              <p><span className="text-slate-500">Manufacturer:</span> {drugQuery.data?.manufacturer ?? "-"}</p>
              <p><span className="text-slate-500">Last analyzed:</span> {drugQuery.data?.latest_report?.created_at ? format(new Date(drugQuery.data.latest_report.created_at), "PPpp") : "Not yet"}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Data Sources</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-[13px] text-slate-700">
              <p>OpenFDA: Active</p>
              <p>Reddit: Active</p>
              <p>ClinicalTrials.gov: Active</p>
            </CardContent>
          </Card>
          <Button asChild aria-label="Return to dashboard" variant="outline" className="w-full">
            <Link href="/dashboard">Back to Dashboard</Link>
          </Button>
        </aside>

        <section>
          <Tabs defaultValue="overview" className="w-full">
            <TabsList>
              <TabsTrigger value="overview" aria-label="Overview tab">Overview</TabsTrigger>
              <TabsTrigger value="gaps" aria-label="Gap analysis tab">Gap Analysis</TabsTrigger>
              <TabsTrigger value="trends" aria-label="Trends tab">Trends</TabsTrigger>
              <TabsTrigger value="reviews" aria-label="Reviews tab">Reviews</TabsTrigger>
              <TabsTrigger value="reports" aria-label="Reports tab">Reports</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4">
              {pageError ? (
                <Card>
                  <CardContent className="p-6 text-[13px] text-red-600">Unable to load drug analysis data: {pageError.message}</CardContent>
                </Card>
              ) : resolvedReport ? (
                <>
                  <DrugOverviewCard
                    perceptionScore={resolvedReport.perceptionScore}
                    trialScore={resolvedReport.trialScore}
                    gapScore={resolvedReport.gapScore}
                    isLoading={analysis.isLoading}
                  />
                  <InsightsList insights={analysis.insights} isLoading={analysis.isLoading} sendPrompt={(prompt) => toast.message(`Ask AI: ${prompt}`)} />
                </>
              ) : (
                <Card>
                  <CardContent className="space-y-2 p-6 text-[13px] text-slate-600">
                    <p>No analysis report found for this drug yet.</p>
                    <p className="text-slate-500">Run Analyze from the dashboard for this exact drug record, then refresh this page.</p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="gaps">
              <GapRadarChart gaps={analysis.gaps} isLoading={analysis.isLoading} />
            </TabsContent>

            <TabsContent value="trends" className="space-y-4">
              <SentimentTrendChart data={trendsQuery.data ?? analysis.trends} onRangeChange={() => undefined} isLoading={analysis.isLoading || trendsQuery.isLoading} />
              <TopicPieChart data={analysis.topics} isLoading={analysis.isLoading} />
            </TabsContent>

            <TabsContent value="reviews">
              <Card>
                <CardHeader>
                  <CardTitle>Reviews (Virtualized)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div ref={parentRef} className="h-[560px] overflow-auto rounded-md border border-slate-200">
                    <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Date</TableHead>
                            <TableHead>Source</TableHead>
                            <TableHead>Sentiment</TableHead>
                            <TableHead>Excerpt</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                            const row = reviewRows[virtualRow.index];
                            return (
                              <TableRow
                                key={row.id}
                                style={{
                                  position: "absolute",
                                  top: 0,
                                  left: 0,
                                  width: "100%",
                                  transform: `translateY(${virtualRow.start}px)`,
                                  height: `${virtualRow.size}px`,
                                }}
                              >
                                <TableCell>{format(row.date, "yyyy-MM-dd")}</TableCell>
                                <TableCell>{row.source}</TableCell>
                                <TableCell>{row.sentiment.toFixed(2)}</TableCell>
                                <TableCell className="max-w-[620px] truncate">{row.excerpt}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="reports">
              <Card>
                <CardHeader>
                  <CardTitle>Generated Reports</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Button aria-label="Download reports as PDF" onClick={() => exportFile("pdf")}>Download PDF</Button>
                    <Button aria-label="Download reports as CSV" variant="outline" onClick={() => exportFile("csv")}>Download CSV</Button>
                  </div>
                  <div className="space-y-2 text-[13px]">
                    {(reportsQuery.data ?? []).length === 0 ? (
                      <p className="text-slate-500">No reports generated for this drug yet.</p>
                    ) : (
                      (reportsQuery.data ?? []).map((report) => (
                        <div key={report.id} className="rounded-md border border-slate-200 p-3">
                          <p className="font-medium">{format(new Date(report.created_at), "PPpp")}</p>
                          <p className="text-slate-600">Perception {(report.perception_score * 100).toFixed(2)}% | Gap {(report.gap_score * 100).toFixed(2)}%</p>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </main>
  );
}
