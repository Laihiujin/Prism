import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ platform: string }> }
) {
  try {
    const { platform } = await params
    const incoming = await request.json().catch(() => ({}))
    const payload: Record<string, any> = {
      account_ids: incoming?.account_ids,
    }

    Object.keys(payload).forEach((key) => {
      if (payload[key] === undefined || payload[key] === null) {
        delete payload[key]
      }
    })

    const response = await fetch(
      `${backendBaseUrl}/api/v1/analytics/collect/${platform}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    )

    const backend = await response.json().catch(() => ({}))

    return NextResponse.json(
      {
        success: response.ok && backend?.success !== false,
        data: backend?.data ?? backend,
        message: backend?.message,
        error: response.ok
          ? backend?.error || backend?.detail
          : backend?.error || backend?.detail || "Collect failed",
      },
      { status: response.ok ? 200 : response.status }
    )
  } catch (error) {
    console.error("Analytics collect platform error:", error)
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 })
  }
}
