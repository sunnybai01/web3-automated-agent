import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const base = process.env.CHAT_API_BASE_URL;
  const query = req.nextUrl.searchParams.toString();
  const response = await fetch(
    `${base}/api/v1/dashboard/schedule-logs${query ? `?${query}` : ""}`,
    {
      method: "GET",
      headers: {
        "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
      },
      cache: "no-store",
    }
  );

  const json = await response.json();
  return NextResponse.json(json, { status: response.status });
}
