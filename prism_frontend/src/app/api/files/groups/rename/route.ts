import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export const runtime = "nodejs"

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const res = await fetch(`${backendBaseUrl}/api/v1/files/groups/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const payload = await res.json().catch(() => ({}))
    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("Failed to rename group:", error)
    return NextResponse.json(
      { success: false, message: "rename group failed" },
      { status: 502 }
    )
  }
}

