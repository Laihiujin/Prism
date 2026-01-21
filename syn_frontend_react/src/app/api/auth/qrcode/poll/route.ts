import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const target = `${backendBaseUrl}/api/v1/auth/qrcode/poll?${searchParams.toString()}`

  try {
    const response = await fetch(target, { method: "GET" })
    const body = await response.text()
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
      },
    })
  } catch (error) {
    return NextResponse.json({ success: false, error: String(error) }, { status: 502 })
  }
}
