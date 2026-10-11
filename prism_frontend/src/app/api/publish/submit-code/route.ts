import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export async function POST(request: Request) {
  const response = await fetch(`${backendBaseUrl}/api/v1/verification/submit-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(await request.json()),
  })
  return NextResponse.json(await response.json(), { status: response.status })
}
