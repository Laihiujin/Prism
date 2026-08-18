import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET() {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/verification/otp-events`, { cache: "no-store" })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("Failed to fetch otp events", error)
    return NextResponse.json({ code: 500, msg: "failed" }, { status: 500 })
  }
}
