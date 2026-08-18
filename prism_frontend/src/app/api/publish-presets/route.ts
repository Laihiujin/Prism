import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET() {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets`, { cache: "no-store" })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      {
        code: response.ok ? 200 : response.status,
        msg: response.ok ? null : (payload as any)?.detail || "failed to load publish presets",
        data: payload,
      },
      { status: 200 }
    )
  } catch (error) {
    console.error("Failed to load publish presets", error)
    return NextResponse.json({ code: 500, msg: "failed to load publish presets", data: {} }, { status: 200 })
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      {
        code: response.ok ? 200 : response.status,
        msg: response.ok ? null : (payload as any)?.detail || "failed to create publish preset",
        data: payload,
      },
      { status: 200 }
    )
  } catch (error) {
    console.error("Failed to create publish preset", error)
    return NextResponse.json({ code: 500, msg: "failed to create publish preset", data: {} }, { status: 200 })
  }
}
