/** BFF health route to validate frontend server runtime. */
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ status: "ok" });
}
