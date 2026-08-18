import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id: taskId } = await params
  if (!taskId) {
    return NextResponse.json({ code: 400, msg: "task id is required" }, { status: 400 })
  }

  try {
    const body = await request.json().catch(() => ({}))
    const response = await fetch(`${backendBaseUrl}/api/dispatch-tasks/${taskId}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("dispatch task publish proxy failed", error)
    return NextResponse.json({ code: 500, msg: "Proxy error" }, { status: 500 })
  }
}
