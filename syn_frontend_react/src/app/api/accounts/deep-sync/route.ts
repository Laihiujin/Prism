import { NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/env"

// Use account status check instead of legacy sync.
export async function POST() {
    try {
        const response = await fetch(`${backendBaseUrl}/api/v1/accounts/check-status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        })

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error("Account status check error:", error)
        return NextResponse.json(
            { success: false, error: String(error) },
            { status: 500 }
        )
    }
}
