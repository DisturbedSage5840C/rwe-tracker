export type APIEnvelope<T> = {
  data: T;
  meta: {
    request_id: string | null;
    next_cursor: string | null;
    prev_cursor: string | null;
    count: number | null;
  };
  errors: Array<{ code: string; message: string }> | null;
};

export type CursorPage<T> = {
  items: T[];
  next_cursor: string | null;
  prev_cursor: string | null;
};

export type OrganizationRead = {
  id: string;
  name: string;
  slug: string;
  created_at: string;
};

export type UserRead = {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
};

export type RegisterRequest = {
  organization_name: string;
  organization_slug: string;
  full_name: string;
  email: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type APIKeyCreateRequest = { name: string };

export type APIKeyCreateResponse = {
  id: string;
  name: string;
  key_prefix: string;
  api_key: string;
  created_at: string;
};

export type APIKeyRead = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  revoked: boolean;
};

export type DrugCreateRequest = {
  name: string;
  indication: string | null;
  manufacturer: string | null;
};

export type PerceptionReportSummary = {
  id: string;
  created_at: string;
  perception_score: number;
  trial_score: number;
  gap_score: number;
  confidence_interval_lower: number | null;
  confidence_interval_upper: number | null;
  methodology_version: string;
};

export type DrugRead = {
  id: string;
  organization_id: string;
  name: string;
  normalized_name: string;
  indication: string | null;
  manufacturer: string | null;
  created_at: string;
};

export type DrugDetailRead = DrugRead & {
  latest_report: PerceptionReportSummary | null;
};

export type PerceptionReportRead = {
  id: string;
  drug_id: string;
  summary: string | null;
  perception_score: number;
  trial_score: number;
  gap_score: number;
  confidence_interval_lower: number | null;
  confidence_interval_upper: number | null;
  sample_size_reviews: number;
  sample_size_social: number;
  methodology_version: string;
  created_at: string;
};

export type AnalyzeTriggerResponse = {
  job_id: string;
  celery_task_id: string;
  status: string;
};

export type AnalyzeJobStatusResponse = {
  job_id: string;
  celery_task_id: string;
  status: string;
  result_payload: Record<string, unknown>;
};

export type DrugComparisonItem = {
  drug_id: string;
  drug_name: string;
  latest_gap_score: number | null;
  latest_perception_score: number | null;
};

export type CompareResponse = {
  items: DrugComparisonItem[];
};

export type TrendPoint = {
  date: string;
  perception_score: number;
  trial_score: number;
  gap_score: number;
};

export type TrendResponse = {
  drug_id: string;
  granularity: "daily" | "weekly" | "monthly";
  points: TrendPoint[];
};

export type GapDimension = {
  dimension: "efficacy" | "safety" | "tolerability" | "convenience" | "quality_of_life";
  clinical_score: number;
  real_world_score: number;
  gap_magnitude: number;
  p_value: number;
  significant: boolean;
};

export type GapResponse = {
  drug_id: string;
  latest_report_id: string | null;
  breakdown: {
    efficacy: number | null;
    safety: number | null;
    tolerability: number | null;
    convenience: number | null;
    quality_of_life: number | null;
  };
};

export type InsightSeverity = "critical" | "high" | "moderate";

export type InsightItem = {
  dimension: GapDimension["dimension"];
  severity: InsightSeverity;
  message: string;
  recommendation: string;
  p_value: number;
};

export type TopicDistributionPoint = {
  name: string;
  value: number;
};

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  skipAuth?: boolean;
};

export class RWEApiClient {
  private readonly baseUrl: string;
  private accessToken: string | null = null;

  constructor(baseUrl: string | undefined) {
    this.baseUrl = (baseUrl ?? "http://localhost:8000").replace(/\/$/, "");
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  private buildUrl(path: string, query?: RequestOptions["query"]): string {
    const url = new URL(`${this.baseUrl}${path}`);
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, String(value));
        }
      });
    }
    return url.toString();
  }

  private async request<T>(path: string, options: RequestOptions = {}, allowRefresh = true): Promise<T> {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (!options.skipAuth && this.accessToken) {
      headers.set("Authorization", `Bearer ${this.accessToken}`);
    }

    const response = await fetch(this.buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      credentials: "include",
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });

    if (response.status === 401 && allowRefresh && !options.skipAuth) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        return this.request<T>(path, options, false);
      }
    }

    if (!response.ok) {
      const fallback = `Request failed with status ${response.status}`;
      const payload = (await response.json().catch(() => null)) as APIEnvelope<unknown> | null;
      const message = payload?.errors?.[0]?.message ?? fallback;
      throw new Error(message);
    }

    return (await response.json()) as T;
  }

  private async refreshAccessToken(): Promise<boolean> {
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });

    if (!response.ok) {
      this.accessToken = null;
      return false;
    }

    const payload = (await response.json()) as { accessToken: string };
    this.accessToken = payload.accessToken;
    return true;
  }

  async register(payload: RegisterRequest): Promise<APIEnvelope<TokenPair>> {
    return this.request<APIEnvelope<TokenPair>>("/auth/register", { method: "POST", body: payload, skipAuth: true });
  }

  async login(payload: LoginRequest): Promise<APIEnvelope<TokenPair>> {
    return this.request<APIEnvelope<TokenPair>>("/auth/token", { method: "POST", body: payload, skipAuth: true });
  }

  async logout(refreshToken: string): Promise<APIEnvelope<{ message: string }>> {
    return this.request<APIEnvelope<{ message: string }>>("/auth/logout", {
      method: "POST",
      body: { refresh_token: refreshToken },
      skipAuth: true,
    });
  }

  async me(): Promise<APIEnvelope<UserRead>> {
    return this.request<APIEnvelope<UserRead>>("/auth/me");
  }

  async createApiKey(payload: APIKeyCreateRequest): Promise<APIEnvelope<APIKeyCreateResponse>> {
    return this.request<APIEnvelope<APIKeyCreateResponse>>("/auth/api-keys", { method: "POST", body: payload });
  }

  async revokeApiKey(keyId: string): Promise<APIEnvelope<APIKeyRead>> {
    return this.request<APIEnvelope<APIKeyRead>>(`/auth/api-keys/${keyId}`, { method: "DELETE" });
  }

  async listDrugs(params?: { cursor?: string; limit?: number; search?: string }): Promise<APIEnvelope<CursorPage<DrugRead>>> {
    return this.request<APIEnvelope<CursorPage<DrugRead>>>("/drugs", {
      query: { cursor: params?.cursor, limit: params?.limit, search: params?.search },
    });
  }

  async createDrug(payload: DrugCreateRequest): Promise<APIEnvelope<DrugRead>> {
    return this.request<APIEnvelope<DrugRead>>("/drugs", { method: "POST", body: payload });
  }

  async getDrug(drugId: string): Promise<APIEnvelope<DrugDetailRead>> {
    return this.request<APIEnvelope<DrugDetailRead>>(`/drugs/${drugId}`);
  }

  async deleteDrug(drugId: string): Promise<APIEnvelope<{ deleted: boolean }>> {
    return this.request<APIEnvelope<{ deleted: boolean }>>(`/drugs/${drugId}`, { method: "DELETE" });
  }

  async listReports(drugId: string, params?: { cursor?: string; limit?: number }): Promise<APIEnvelope<CursorPage<PerceptionReportRead>>> {
    return this.request<APIEnvelope<CursorPage<PerceptionReportRead>>>(`/drugs/${drugId}/reports`, {
      query: { cursor: params?.cursor, limit: params?.limit },
    });
  }

  async exportReportsCsv(drugId: string): Promise<Blob> {
    const response = await fetch(this.buildUrl(`/drugs/${drugId}/reports`, { format: "csv" }), {
      method: "GET",
      headers: this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : undefined,
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("Unable to export CSV report");
    }
    return response.blob();
  }

  async exportReportsPdf(drugId: string): Promise<Blob> {
    const response = await fetch(this.buildUrl(`/drugs/${drugId}/reports`, { format: "pdf" }), {
      method: "GET",
      headers: this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : undefined,
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("Unable to export PDF report");
    }
    return response.blob();
  }

  async triggerAnalysis(drugId: string): Promise<APIEnvelope<AnalyzeTriggerResponse>> {
    return this.request<APIEnvelope<AnalyzeTriggerResponse>>(`/drugs/${drugId}/analyze`, { method: "POST" });
  }

  async pollAnalysisJob(drugId: string, jobId: string): Promise<APIEnvelope<AnalyzeJobStatusResponse>> {
    return this.request<APIEnvelope<AnalyzeJobStatusResponse>>(`/drugs/${drugId}/analyze/${jobId}`);
  }

  async compareDrugs(drugIds: string[]): Promise<APIEnvelope<CompareResponse>> {
    return this.request<APIEnvelope<CompareResponse>>("/analysis/compare", {
      query: { drug_ids: drugIds.join(",") },
    });
  }

  async trends(drugId: string, params?: { days?: number; granularity?: "daily" | "weekly" | "monthly" }): Promise<APIEnvelope<TrendResponse>> {
    return this.request<APIEnvelope<TrendResponse>>(`/analysis/trends/${drugId}`, {
      query: { days: params?.days ?? 90, granularity: params?.granularity ?? "daily" },
    });
  }

  async gaps(drugId: string): Promise<APIEnvelope<GapResponse>> {
    return this.request<APIEnvelope<GapResponse>>(`/analysis/gaps/${drugId}`);
  }
}

export const api = new RWEApiClient(process.env.NEXT_PUBLIC_API_URL);
