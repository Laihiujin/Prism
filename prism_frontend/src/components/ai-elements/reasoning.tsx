"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

export function Reasoning({
    children,
    duration
}: {
    children: React.ReactNode
    duration?: number
}) {
    return <div className="text-xs text-white/50 mb-2">{children}</div>
}

export function ReasoningTrigger() {
    return (
        <span className="text-xs text-white/50 hover:text-white/70">
            💭 思考过程
        </span>
    )
}

export function ReasoningContent({ children }: { children: React.ReactNode }) {
    return (
        <div className="mt-2 p-3 bg-black/30 rounded text-xs text-white/70">
            {children}
        </div>
    )
}
