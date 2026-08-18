import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export const runtime = "nodejs"

export async function POST() {
  try {
    const res = await fetch(`${backendBaseUrl}/api/v1/files/sync`, { method: "POST" })
    const payload = await res.json().catch(() => ({}))
    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("Failed to sync files:", error)
    return NextResponse.json(
      { success: false, message: "sync failed", error: String(error) },
      { status: 502 }
    )
  }
}
