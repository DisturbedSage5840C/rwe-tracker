import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const REFRESH_COOKIE_KEY = "rwe_refresh_token";

export async function POST(request: Request) {
  const body = (await request.json()) as { refreshToken?: string };
  if (!body.refreshToken) {
    return NextResponse.json({ error: "Missing refresh token" }, { status: 400 });
  }

  cookies().set(REFRESH_COOKIE_KEY, body.refreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14,
  });

  return NextResponse.json({ ok: true });
}

export async function DELETE() {
  cookies().set(REFRESH_COOKIE_KEY, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return NextResponse.json({ ok: true });
}
