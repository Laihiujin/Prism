import { NextRequest, NextResponse } from "next/server";

import { backendBaseUrl } from "@/lib/env";

export async function GET(request: NextRequest) {
  try {
    const queryString = request.nextUrl.searchParams.toString();
    const url = queryString
      ? `${backendBaseUrl}/api/v1/analytics/?${queryString}`
      : `${backendBaseUrl}/api/v1/analytics/`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    const payload = await response.json().catch(() => ({}));

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("Analytics route error:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

