import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const body = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      {
        code: response.ok ? 200 : response.status,
        msg: response.ok ? null : (payload as any)?.detail || "failed to update publish preset",
        data: payload,
      },
      { status: 200 }
    )
  } catch (error) {
    console.error("Failed to update publish preset", error)
    return NextResponse.json({ code: 500, msg: "failed to update publish preset", data: {} }, { status: 200 })
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/publish/presets/${id}`, {
      method: "DELETE",
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      {
        code: response.ok ? 200 : response.status,
        msg: response.ok ? null : (payload as any)?.detail || "failed to delete publish preset",
        data: payload,
      },
      { status: 200 }
    )
  } catch (error) {
    console.error("Failed to delete publish preset", error)
    return NextResponse.json({ code: 500, msg: "failed to delete publish preset", data: {} }, { status: 200 })
  }
}
