"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"

export function Tool({
    children,
    name,
    status,
    className
}: {
    children: React.ReactNode
    name: string
    status?: "input-available" | "in-progress" | "completed" | "error"
    className?: string
}) {
    return (
        <Card className={cn("bg-black/40 border-primary/20 p-3 space-y-2", className)}>
            {children}
        </Card>
    )
}

export function ToolHeader({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-2">{children}</div>
}

export function ToolName({ children }: { children: React.ReactNode }) {
    return <span className="text-white/90 font-medium text-xs">{children}</span>
}

export function ToolStatus({ status }: { status: string }) {
    const icons = {
        'completed': '✅',
        'in-progress': '⏰',
        'error': '❌'
    }
    return <span className="text-xs ml-auto">{icons[status as keyof typeof icons] || '○'}</span>
}

export function ToolResult({ children }: { children: React.ReactNode }) {
    return (
        <div className="text-green-400/80 text-xs font-mono bg-black/30 rounded p-2 max-h-32 overflow-y-auto">
            {children}
        </div>
    )
}
