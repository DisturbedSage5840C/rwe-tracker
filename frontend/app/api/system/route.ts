import { NextResponse } from "next/server";

type ServiceState = {
  ok: boolean;
  detail: string;
};

export async function GET() {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const nlpBase = (process.env.NEXT_PUBLIC_NLP_URL ?? "http://localhost:8001").replace(/\/$/, "");

  const apiState: ServiceState = { ok: false, detail: "unreachable" };
  const nlpState: ServiceState = { ok: false, detail: "unreachable" };

  try {
    const response = await fetch(`${apiBase}/health`, { cache: "no-store" });
    const payload = (await response.json().catch(() => null)) as { data?: { status?: string } } | null;
    apiState.ok = response.ok && payload?.data?.status === "ok";
    apiState.detail = apiState.ok ? "ok" : `http_${response.status}`;
  } catch {
    apiState.ok = false;
    apiState.detail = "network_error";
  }

  try {
    const response = await fetch(`${nlpBase}/health`, { cache: "no-store" });
    const payload = (await response.json().catch(() => null)) as { status?: string } | null;
    nlpState.ok = response.ok && payload?.status === "ok";
    nlpState.detail = nlpState.ok ? "ok" : `http_${response.status}`;
  } catch {
    nlpState.ok = false;
    nlpState.detail = "network_error";
  }

  return NextResponse.json({
    frontend: { ok: true, detail: "ok" },
    api: apiState,
    nlp: nlpState,
    overall: apiState.ok && nlpState.ok ? "connected" : "degraded",
  });
}