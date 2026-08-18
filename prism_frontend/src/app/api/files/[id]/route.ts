import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export const runtime = "nodejs"

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    console.log(`[Next.js API] DELETE /api/files/${id} - 开始转发到后端`)

    const backendUrl = `${backendBaseUrl}/api/v1/files/${encodeURIComponent(id)}`
    console.log(`[Next.js API] 后端URL: ${backendUrl}`)

    const res = await fetch(backendUrl, {
      method: "DELETE",
    })

    console.log(`[Next.js API] 后端响应: ${res.status} ${res.statusText}`)

    const payload = await res.json().catch(() => ({}))
    console.log(`[Next.js API] 后端响应体:`, payload)

    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("[Next.js API] DELETE 失败:", error)
    return NextResponse.json(
      { success: false, message: "delete failed" },
      { status: 502 }
    )
  }
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()
    const res = await fetch(`${backendBaseUrl}/api/v1/files/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const payload = await res.json().catch(() => ({}))
    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("Failed to update file:", error)
    return NextResponse.json(
      { success: false, message: "update failed" },
      { status: 502 }
    )
  }
}
