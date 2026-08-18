"use client"

import { cn } from "@/lib/utils"
import { LayoutGrid } from "lucide-react"

export type PublishMode = "matrix"

interface PublishModeSelectorProps {
    selected: PublishMode
    onSelect: (mode: PublishMode) => void
}

export function PublishModeSelector({ selected, onSelect }: PublishModeSelectorProps) {
    const mode = {
        id: "matrix" as PublishMode,
        title: "矩阵发布",
        description: "多账号、多素材批量分发，AI 自动匹配文案",
        icon: LayoutGrid,
    }

    const isSelected = selected === mode.id
    const Icon = mode.icon

    return (
        <div className="w-md">
            <div
                className={cn(
                    "relative flex items-start gap-4 p-4 rounded-xl border-2 transition-all duration-200",
                    "border-primary bg-primary/10 shadow-[0_0_20px_-10px_rgba(var(--primary),0.3)]"
                )}
            >
                <div className={cn(
                    "p-3 rounded-lg transition-colors",
                    "bg-primary text-primary-foreground"
                )}>
                    <Icon className="w-6 h-6" />
                </div>

                <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                        <h3 className="font-medium text-primary">
                            {mode.title}
                        </h3>
                        <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse" />
                    </div>
                    <p className="text-xs text-white/50 leading-relaxed">
                        {mode.description}
                    </p>
                </div>
            </div>
        </div>
    )
}
