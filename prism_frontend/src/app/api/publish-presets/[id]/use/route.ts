import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets/${id}/use`, {
      method: "POST",
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      {
        code: response.ok ? 200 : response.status,
        msg: response.ok ? null : (payload as any)?.detail || "failed to update preset usage",
        data: payload,
      },
      { status: 200 }
    )
  } catch (error) {
    console.error("Failed to mark preset as used", error)
    return NextResponse.json({ code: 500, msg: "failed to update preset usage", data: {} }, { status: 200 })
  }
}
