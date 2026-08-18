import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET() {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/plans`, { cache: "no-store" })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json({ code: 200, msg: null, data: payload }, { status: 200 })
  } catch (error) {
    console.error("Failed to fetch plans", error)
    return NextResponse.json({ code: 500, msg: "failed to fetch plans", data: [] }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/plans`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json(payload, { status: response.status })
    }
    return NextResponse.json({ code: 200, msg: null, data: payload }, { status: 200 })
  } catch (error) {
    console.error("Failed to create plan", error)
    return NextResponse.json({ code: 500, msg: "failed to create plan" }, { status: 500 })
  }
}
