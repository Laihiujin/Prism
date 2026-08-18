import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url)
        const limit = searchParams.get('limit') || '50'
        const status = searchParams.get('status')

        const params = new URLSearchParams({ limit })
        if (status) params.append('status', status)

        const response = await fetch(`${backendBaseUrl}/api/v1/tasks/list?${params}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error("Task list error:", error)
        return NextResponse.json(
            { success: false, error: String(error) },
            { status: 500 }
        )
    }
}
