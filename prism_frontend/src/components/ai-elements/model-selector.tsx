"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

export function ModelSelector({
    children,
    open,
    onOpenChange
}: {
    children: React.ReactNode
    open?: boolean
    onOpenChange?: (open: boolean) => void
}) {
    return <div className="relative">{children}</div>
}

export function ModelSelectorTrigger({
    children,
    asChild
}: {
    children: React.ReactNode
    asChild?: boolean
}) {
    return <div>{children}</div>
}

export function ModelSelectorContent({ children }: { children: React.ReactNode }) {
    return (
        <div className="absolute bottom-full mb-2 w-64 bg-black/95 border border-white/10 rounded-lg p-2">
            {children}
        </div>
    )
}

export function ModelSelectorInput({ placeholder }: { placeholder?: string }) {
    return (
        <input
            type="text"
            placeholder={placeholder}
            className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded text-white text-sm mb-2"
        />
    )
}

export function ModelSelectorList({ children }: { children: React.ReactNode }) {
    return <div className="space-y-1">{children}</div>
}

export function ModelSelectorEmpty({ children }: { children: React.ReactNode }) {
    return <div className="text-white/50 text-sm p-2">{children}</div>
}

export function ModelSelectorGroup({
    children,
    heading
}: {
    children: React.ReactNode
    heading?: string
}) {
    return (
        <div className="space-y-1">
            {heading && <div className="text-white/70 text-xs font-medium px-2 py-1">{heading}</div>}
            {children}
        </div>
    )
}

export function ModelSelectorItem({
    children,
    value,
    onSelect
}: {
    children: React.ReactNode
    value: string
    onSelect: () => void
}) {
    return (
        <button
            onClick={onSelect}
            className="w-full flex items-center gap-2 px-2 py-2 hover:bg-white/10 rounded text-sm text-white text-left"
        >
            {children}
        </button>
    )
}

export function ModelSelectorLogo({ provider }: { provider: string }) {
    return (
        <div className="w-4 h-4 rounded bg-primary/20 flex items-center justify-center text-xs">
            {provider[0].toUpperCase()}
        </div>
    )
}

export function ModelSelectorLogoGroup({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center gap-1 ml-auto">{children}</div>
}

export function ModelSelectorName({ children }: { children: React.ReactNode }) {
    return <span className="flex-1">{children}</span>
}
