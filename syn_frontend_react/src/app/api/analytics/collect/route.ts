import { NextRequest, NextResponse } from "next/server";

import { backendBaseUrl } from "@/lib/env";

/**
 * Trigger backend analytics collection.
 * Default: collect all videos for all valid accounts (mode=accounts).
 */
export async function POST(request: NextRequest) {
  try {
    const incoming = await request.json().catch(() => ({}));
    const payload: Record<string, any> = {
      mode: incoming?.mode ?? "accounts",
      platform: incoming?.platform,
      account_ids: incoming?.account_ids,
    };

    // drop undefined/null fields to keep payload clean
    Object.keys(payload).forEach((key) => {
      if (payload[key] === undefined || payload[key] === null) {
        delete payload[key];
      }
    });

    const response = await fetch(`${backendBaseUrl}/api/v1/analytics/collect`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const backend = await response.json().catch(() => ({}));

    return NextResponse.json(
      {
        success: response.ok && backend?.success !== false,
        data: backend?.data ?? backend,
        message: backend?.message,
        error: response.ok ? backend?.error || backend?.detail : backend?.error || backend?.detail || "Collect failed",
      },
      { status: response.ok ? 200 : response.status }
    );
  } catch (error) {
    console.error("Analytics collect error:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
