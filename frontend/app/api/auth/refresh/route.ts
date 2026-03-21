import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import type { APIEnvelope, TokenPair } from "@/lib/api";

const REFRESH_COOKIE_KEY = "rwe_refresh_token";

export async function POST() {
  const refreshToken = cookies().get(REFRESH_COOKIE_KEY)?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ error: "Unable to refresh token" }, { status: 401 });
  }

  const payload = (await response.json()) as APIEnvelope<TokenPair>;
  cookies().set(REFRESH_COOKIE_KEY, payload.data.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14,
  });

  return NextResponse.json({ accessToken: payload.data.access_token });
}
