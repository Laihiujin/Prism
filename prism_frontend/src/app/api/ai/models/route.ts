import { NextResponse } from "next/server"

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const baseUrl = (searchParams.get("baseUrl") || "").replace(/\/$/, "")
    const apiKey = searchParams.get("apiKey") || ""
    if (!baseUrl || !apiKey) {
      return NextResponse.json({ error: "missing baseUrl or apiKey" }, { status: 400 })
    }
    const response = await fetch(`${baseUrl}/v1/models`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      cache: "no-store",
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json({ error: payload?.error ?? "models request failed" }, { status: response.status })
    }
    const list: Array<{ id?: string; name?: string }> = Array.isArray(payload?.data)
      ? payload.data
      : Array.isArray(payload?.models)
        ? payload.models
        : []
    const models = list
      .map((m) => m?.id || m?.name)
      .filter((v): v is string => Boolean(v))
    return NextResponse.json({ data: models, total: models.length, timestamp: Date.now() })
  } catch (error) {
    return NextResponse.json({ error: "failed to query models" }, { status: 502 })
  }
}

