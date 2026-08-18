import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url)
  const taskId = searchParams.get("task_id")

  if (!taskId) {
    return NextResponse.json({ code: 400, msg: "task_id is required" }, { status: 400 })
  }

  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "DELETE",
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("Failed to delete distribution task", error)
    return NextResponse.json({ code: 500, msg: "Proxy error" }, { status: 500 })
  }
}
