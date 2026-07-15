import { NextResponse } from "next/server";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ eventId: string }> }
) {
  const { eventId } = await params;
  const base = process.env.CHAT_API_BASE_URL;
  const response = await fetch(
    `${base}/api/v1/dashboard/opportunities/${eventId}`,
    {
      method: "DELETE",
      headers: {
        "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
      },
      cache: "no-store",
    }
  );

  const json = await response.json();
  return NextResponse.json(json, { status: response.status });
}
