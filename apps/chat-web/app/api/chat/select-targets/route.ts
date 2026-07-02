import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const base = process.env.CHAT_API_BASE_URL;

  const response = await fetch(`${base}/api/v1/chat/select-targets`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    body: JSON.stringify(payload),
  });

  const json = await response.json();
  return NextResponse.json(json, { status: response.status });
}
