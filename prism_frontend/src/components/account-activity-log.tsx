"use client"

import { Activity, CheckCircle2, XCircle, Shield, Settings, LogIn } from "lucide-react"

export interface ActivityLogItem {
    id: string
    title: string
    description: string
    time: string
    type: "success" | "warning" | "error" | "info"
    icon?: any
}

interface AccountActivityLogProps {
    logs: ActivityLogItem[]
}

export function AccountActivityLog({ logs }: AccountActivityLogProps) {
    return (
        <div className="space-y-0">
            {logs.length === 0 && (
                <p className="text-sm text-white/60">暂无事件，等待新的自动化日志...</p>
            )}
            {logs.map((item, index) => {
                let Icon = Activity
                let colorClass = "text-blue-400"
                let bgClass = "bg-blue-400/10 border-blue-400/20"

                if (item.type === "success") {
                    Icon = CheckCircle2
                    colorClass = "text-emerald-400"
                    bgClass = "bg-emerald-400/10 border-emerald-400/20"
                } else if (item.type === "error") {
                    Icon = XCircle
                    colorClass = "text-red-400"
                    bgClass = "bg-red-400/10 border-red-400/20"
                } else if (item.type === "warning") {
                    Icon = Shield
                    colorClass = "text-amber-400"
                    bgClass = "bg-amber-400/10 border-amber-400/20"
                }

                return (
                    <div key={item.id || index} className="relative pl-8 pb-8 last:pb-0 group">
                        {/* Line */}
                        {index !== logs.length - 1 && (
                            <div className="absolute left-[11px] top-8 bottom-0 w-px bg-white/10 group-hover:bg-white/20 transition-colors" />
                        )}

                        {/* Dot */}
                        <div className={`absolute left-0 top-1 h-6 w-6 rounded-full border ${bgClass} flex items-center justify-center shadow-sm`}>
                            <Icon className={`h-3 w-3 ${colorClass}`} />
                        </div>

                        <div className="flex flex-col gap-1.5">
                            <div className="flex items-center justify-between">
                                <p className="text-sm font-medium text-white group-hover:text-primary transition-colors">{item.title}</p>
                                <span className="text-xs text-white/40 font-mono">{item.time}</span>
                            </div>
                            <p className="text-xs text-white/60 leading-relaxed">{item.description}</p>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}
