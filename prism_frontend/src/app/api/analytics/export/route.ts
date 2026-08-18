import { NextRequest } from "next/server";

import { backendBaseUrl } from "@/lib/env";

export async function GET(request: NextRequest) {
  const queryString = request.nextUrl.searchParams.toString();
  const url = queryString
    ? `${backendBaseUrl}/api/v1/analytics/export?${queryString}`
    : `${backendBaseUrl}/api/v1/analytics/export`;

  const response = await fetch(url, { method: "GET" });
  const blob = await response.blob();

  const headers = new Headers(response.headers);
  // Ensure download works even if backend doesn't set it
  if (!headers.get("Content-Disposition")) {
    headers.set("Content-Disposition", "attachment");
  }

  return new Response(blob, {
    status: response.status,
    headers,
  });
}

