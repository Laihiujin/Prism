import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET() {
  try {
    const res = await fetch(`${backendBaseUrl}/api/v1/tasks/distribution`, {
      // Ensure this runs server-side without caching stale task lists
      cache: "no-store",
    })

    if (!res.ok) {
      return NextResponse.json({ code: res.status, msg: "Failed to fetch tasks", data: [] }, { status: res.status })
    }

    const payload = await res.json()
    // Backend already returns { code, msg, data }
    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("distribution task proxy failed", error)
    return NextResponse.json({ code: 500, msg: "Proxy error", data: [] }, { status: 500 })
  }
}
