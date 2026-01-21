import { NextResponse } from "next/server"
import { backendBaseUrl } from "@/lib/env"

export const runtime = "nodejs"

export async function POST(request: Request) {
  try {
    const formData = await request.formData()
    const res = await fetch(`${backendBaseUrl}/api/v1/files/upload-save`, {
      method: "POST",
      body: formData,
    })
    const payload = await res.json().catch(() => ({}))
    return NextResponse.json(payload, { status: res.status })
  } catch (error) {
    console.error("Failed to upload file:", error)
    return NextResponse.json(
      { success: false, message: "upload failed" },
      { status: 502 }
    )
  }
}
