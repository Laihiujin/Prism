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
    blue: 'bg-blue-500/10 text-blue-400',
    pink: 'bg-pink-500/10 text-pink-400',
    cyan: 'bg-cyan-500/10 text-cyan-400',
    green: 'bg-green-500/10 text-green-400',
    orange: 'bg-orange-500/10 text-orange-400',
}

export function StatsCard({ title, value, icon, color = 'blue', onClick, isActive }: StatsCardProps) {
    return (
        <Card
            className={cn(
                "border-black bg-black/40 transition-all duration-200",
                onClick && "cursor-pointer hover:bg-black/60",
                isActive && "ring-2 ring-primary/50 border-primary/50 bg-black/60 shadow-[0_0_15px_rgba(124,77,255,0.1)]"
            )}
            onClick={onClick}
        >
            <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                    <span className={cn("text-sm transition-colors", isActive ? "text-white" : "text-white/60")}>{title}</span>
                    <div className={cn("p-2 rounded-lg transition-all", colorClasses[color], isActive && "scale-110")}>
                        {icon}
                    </div>
                </div>
                <div className={cn("text-2xl font-semibold transition-colors", isActive && "text-primary")}>{value}</div>
            </CardContent>
        </Card>
    )
}
