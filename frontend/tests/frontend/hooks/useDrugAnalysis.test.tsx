import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import type { ReactNode } from "react";
import { SWRConfig } from "swr";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { useDrugAnalysis, usePollingJob } from "@/lib/hooks/useDrugAnalysis";
import { useAuthStore } from "@/lib/store/auth-store";

const wrapper = ({ children }: { children: ReactNode }) => {
  return <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{children}</SWRConfig>;
};

describe("useDrugAnalysis", () => {
  it("returns isLoading=true on initial render", () => {
    useAuthStore.setState({
      user: null,
      org: null,
      accessToken: "token",
      activeDrugId: null,
      setAuth: vi.fn(),
      setActiveDrug: vi.fn(),
      clearAuth: vi.fn(),
    });

    vi.spyOn(api, "listReports").mockReturnValue(new Promise(() => undefined));
    vi.spyOn(api, "trends").mockResolvedValue({ data: { drug_id: "d1", granularity: "daily", points: [] }, meta: { request_id: null, next_cursor: null, prev_cursor: null, count: null }, errors: null });
    vi.spyOn(api, "gaps").mockResolvedValue({ data: { drug_id: "d1", latest_report_id: null, breakdown: { efficacy: 0, safety: 0, tolerability: 0, convenience: 0, quality_of_life: 0 } }, meta: { request_id: null, next_cursor: null, prev_cursor: null, count: null }, errors: null });

    const { result } = renderHook(() => useDrugAnalysis("d1"), { wrapper });
    expect(result.current.isLoading).toBe(true);
  });

  it("stops polling when job status is complete", async () => {
    useAuthStore.setState({
      user: null,
      org: null,
      accessToken: "token",
      activeDrugId: null,
      setAuth: vi.fn(),
      setActiveDrug: vi.fn(),
      clearAuth: vi.fn(),
    });

    const pollSpy = vi.spyOn(api, "pollAnalysisJob").mockResolvedValue({
      data: { job_id: "j1", celery_task_id: "c1", status: "complete", result_payload: { progress: 100 } },
      meta: { request_id: null, next_cursor: null, prev_cursor: null, count: null },
      errors: null,
    });

    const { result } = renderHook(() => usePollingJob("j1", "d1"), { wrapper });

    await waitFor(() => {
      expect(result.current.status).toBe("complete");
      expect(result.current.progress).toBe(100);
    });
    expect(pollSpy).toHaveBeenCalledTimes(1);
  });

  it("returns error state on API 500", async () => {
    useAuthStore.setState({
      user: null,
      org: null,
      accessToken: "token",
      activeDrugId: null,
      setAuth: vi.fn(),
      setActiveDrug: vi.fn(),
      clearAuth: vi.fn(),
    });

    vi.spyOn(api, "listReports").mockRejectedValue(new Error("Internal server error"));
    vi.spyOn(api, "trends").mockResolvedValue({ data: { drug_id: "d1", granularity: "daily", points: [] }, meta: { request_id: null, next_cursor: null, prev_cursor: null, count: null }, errors: null });
    vi.spyOn(api, "gaps").mockResolvedValue({ data: { drug_id: "d1", latest_report_id: null, breakdown: { efficacy: 0, safety: 0, tolerability: 0, convenience: 0, quality_of_life: 0 } }, meta: { request_id: null, next_cursor: null, prev_cursor: null, count: null }, errors: null });

    const { result } = renderHook(() => useDrugAnalysis("d1"), { wrapper });

    await waitFor(() => {
      expect(result.current.error?.message).toContain("Internal server error");
    });
  });
});
