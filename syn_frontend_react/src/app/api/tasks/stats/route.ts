import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

export async function GET() {
    try {
        const response = await fetch(`${backendBaseUrl}/api/v1/tasks/stats`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error("Task stats error:", error)
        return NextResponse.json(
            { success: false, error: String(error) },
            { status: 500 }
        )
    }
}
