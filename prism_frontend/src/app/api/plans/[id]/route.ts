import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/plans/${id}`, { cache: "no-store" })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json(payload, { status: response.status })
    }
    const plan = payload?.result?.plan ?? payload?.plan ?? payload
    return NextResponse.json({ code: 200, msg: null, data: plan }, { status: 200 })
  } catch (error) {
    console.error("Failed to get plan", error)
    return NextResponse.json({ code: 500, msg: "failed to get plan" }, { status: 500 })
  }
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const body = await request.json()
    const response = await fetch(`${backendBaseUrl}/api/v1/plans/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("Failed to update plan", error)
    return NextResponse.json({ code: 500, msg: "failed to update plan" }, { status: 500 })
  }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/plans/${id}`, { method: "DELETE", cache: "no-store" })
    const payload = await response.json().catch(() => ({}))

    // Try to push to recovery (best-effort)
    try {
      const planRes = await fetch(`${backendBaseUrl}/api/v1/plans/${id}`)
      const planPayload = await planRes.json().catch(() => ({}))
      const plan = planPayload?.result?.plan ?? planPayload?.plan ?? null
      if (plan) {
        await fetch(`${backendBaseUrl}/api/v1/recovery/add`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: id, type: "plan", payload: plan }),
        })
      }
    } catch (err) {
      console.warn("Recovery add failed", err)
    }

    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    console.error("Failed to delete plan", error)
    return NextResponse.json({ code: 500, msg: "failed to delete plan" }, { status: 500 })
  }
}
