import { NextRequest, NextResponse } from "next/server";

import { backendBaseUrl } from "@/lib/env";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const queryString = searchParams.toString();

    // FastAPI endpoint: /api/v1/analytics/ (returns summary + videos + chartData)
    const url = queryString
      ? `${backendBaseUrl}/api/v1/analytics/?${queryString}`
      : `${backendBaseUrl}/api/v1/analytics/`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    const payload = await response.json();

    return NextResponse.json({
      success: true,
      data: payload?.videos ?? payload?.data ?? [],
      summary: payload?.summary ?? null,
      chartData: payload?.chartData ?? null,
    });
  } catch (error) {
    console.error("Analytics videos error:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
