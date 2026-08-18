import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export async function POST(request: Request) {
  try {
    const payload = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    })

    const data = await response.json().catch(() => ({}))
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error("Failed to proxy batch publish:", error)
    return NextResponse.json({ detail: "Failed to proxy batch publish" }, { status: 500 })
  }
}
