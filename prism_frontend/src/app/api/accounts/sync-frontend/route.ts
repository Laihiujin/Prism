import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function POST(request: Request) {
  try {
    const payload = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/accounts/prune-by-frontend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload ?? {}),
    })

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Sync frontend accounts error:", error)
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    )
  }
}
