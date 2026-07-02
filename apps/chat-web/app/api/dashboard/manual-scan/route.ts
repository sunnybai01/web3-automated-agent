import { NextResponse } from "next/server";

export async function GET() {
  const base = process.env.CHAT_API_BASE_URL;
  const response = await fetch(`${base}/api/v1/dashboard/manual-scan`, {
    method: "GET",
    headers: {
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    cache: "no-store",
  });

  const json = await response.json();
  return NextResponse.json(json, { status: response.status });
}

export async function POST() {
  const base = process.env.CHAT_API_BASE_URL;
  const response = await fetch(`${base}/api/v1/dashboard/manual-scan`, {
    method: "POST",
    headers: {
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    cache: "no-store",
  });

  const json = await response.json();
  return NextResponse.json(json, { status: response.status });
}
