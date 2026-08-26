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
    return <div className="text-xs text-muted-foreground mb-2">{children}</div>
}

export function ReasoningTrigger() {
    return (
        <span className="text-xs text-muted-foreground hover:text-foreground/70">
            💭 思考过程
        </span>
    )
}

export function ReasoningContent({ children }: { children: React.ReactNode }) {
    return (
        <div className="mt-2 p-3 bg-card/30 rounded text-xs text-foreground/70">
            {children}
        </div>
    )
}
