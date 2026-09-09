"use client"

import { cn } from "@/lib/utils"
import { LayoutGrid, Images, Layers } from "lucide-react"

export type PublishMode = "matrix" | "note" | "bilibili"

interface PublishModeSelectorProps {
    selected: PublishMode
    onSelect: (mode: PublishMode) => void
}

const MODES: { id: PublishMode; title: string; description: string; icon: typeof LayoutGrid }[] = [
    {
        id: "matrix",
        title: "矩阵发布",
        description: "多账号、多素材批量分发，AI 自动匹配文案",
        icon: LayoutGrid,
    },
    {
        id: "note",
        title: "图文发布",
        description: "一组图片 = 一条图文/笔记，多平台多账号分发",
        icon: Images,
    },
    {
        id: "bilibili",
        title: "B站分P",
        description: "多视频合并为一个稿件（P1..Pn 顺序上传）",
        icon: Layers,
    },
]

export function PublishModeSelector({ selected, onSelect }: PublishModeSelectorProps) {
    return (
        <div className="flex flex-wrap gap-3 w-full">
            {MODES.map((mode) => {
                const isSelected = selected === mode.id
                const Icon = mode.icon
                return (
                    <button
                        key={mode.id}
                        onClick={() => onSelect(mode.id)}
                        className={cn(
                            "relative flex items-start gap-4 p-4 rounded-xl border-2 transition-all duration-200 text-left flex-1 min-w-[260px]",
                            isSelected
                                ? "border-primary bg-black shadow-[0_0_20px_-10px_rgba(var(--primary),0.3)]"
                                : "border-border/70 bg-card hover:bg-accent/40"
                        )}
                    >
                        <div className={cn(
                            "p-3 rounded-lg transition-colors",
                            isSelected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        )}>
                            <Icon className="w-6 h-6" />
                        </div>

                        <div className="flex-1 space-y-1">
                            <div className="flex items-center justify-between">
                                <h3 className={cn("font-medium", isSelected ? "text-primary" : "text-foreground")}>
                                    {mode.title}
                                </h3>
                                <span className={cn(
                                    "flex h-2 w-2 rounded-full",
                                    isSelected ? "bg-primary animate-pulse" : "bg-muted-foreground/30"
                                )} />
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                {mode.description}
                            </p>
                        </div>
                    </button>
                )
            })}
        </div>
    )
}
