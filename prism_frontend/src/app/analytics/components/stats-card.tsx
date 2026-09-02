"use client"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface StatsCardProps {
    title: string
    value: string
    icon: React.ReactNode
    color?: 'blue' | 'pink' | 'cyan' | 'green' | 'orange'
    onClick?: () => void
    isActive?: boolean
}

const colorClasses = {
    blue: 'bg-black text-white',
    pink: 'bg-black text-white',
    cyan: 'bg-black text-white',
    green: 'bg-black text-white',
    orange: 'bg-black text-white',
}

export function StatsCard({ title, value, icon, color = 'blue', onClick, isActive }: StatsCardProps) {
    return (
        <Card
            className={cn(
                "border-border bg-card/40 transition-all duration-200",
                onClick && "cursor-pointer hover:bg-card/60",
                isActive && "ring-2 ring-primary/50 border-primary/50 bg-card/60 shadow-[0_0_15px_rgba(124,77,255,0.1)]"
            )}
            onClick={onClick}
        >
            <CardContent className="p-3">
                <div className="flex items-center justify-between mb-1">
                    <span className={cn("font-terminal text-[10px] uppercase tracking-[0.08em] transition-colors", isActive ? "text-foreground" : "text-muted-foreground")}>{title}</span>
                    <div className={cn("p-1 transition-all", colorClasses[color], isActive && "scale-110")}>
                        {icon}
                    </div>
                </div>
                <div className={cn("text-xl font-semibold transition-colors", isActive && "text-primary")}>{value}</div>
            </CardContent>
        </Card>
    )
}
