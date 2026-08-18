"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

export function Message({
    children,
    from,
    className
}: {
    children: React.ReactNode
    from: "user" | "assistant"
    className?: string
}) {
    return (
        <div className={cn(
            "flex gap-3 text-sm",
            from === "user" ? "flex-row-reverse" : "flex-row",
            className
        )}>
            {children}
        </div>
    )
}

export function MessageContent({ children, className }: { children: React.ReactNode; className?: string }) {
    return <div className={cn("flex flex-col gap-2 max-w-[85%]", className)}>{children}</div>
}

export function MessageResponse({ children }: { children: React.ReactNode }) {
    return <div className="prose prose-sm max-w-none">{children}</div>
}
