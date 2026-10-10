"use client"
import { useEffect, useState } from "react"
import { formatBeijingDateTime } from "@/lib/time"

function timestamp(value?: string) {
    if (!value) return NaN
    const normalized = value.replace(" ", "T")
    return Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized) ? normalized : `${normalized}+08:00`)
}
function duration(milliseconds: number) {
    const seconds = Math.max(0, Math.floor(milliseconds / 1000))
    return `${Math.floor(seconds / 3600)}时${Math.floor(seconds % 3600 / 60)}分${seconds % 60}秒`
}
export function TaskExecutionTime({ task }: { task: { createdAt: string; scheduledAt?: string; startedAt?: string; completedAt?: string; status: string } }) {
    const [now, setNow] = useState(() => Date.now())
    const active = ["pending", "scheduled", "running"].includes(task.status)
    useEffect(() => {
        if (!active) return
        const timer = setInterval(() => setNow(Date.now()), 1000)
        return () => clearInterval(timer)
    }, [active])
    const scheduled = timestamp(task.scheduledAt)
    const started = timestamp(task.startedAt)
    const completed = timestamp(task.completedAt)
    return <div className="space-y-1 text-xs text-zinc-400">
        <div>创建 · {formatBeijingDateTime(task.createdAt)}</div>
        {task.scheduledAt && <div>计划 · {formatBeijingDateTime(task.scheduledAt)}</div>}
        {task.startedAt && <div>开始 · {formatBeijingDateTime(task.startedAt)}</div>}
        {task.completedAt && <div>结束 · {formatBeijingDateTime(task.completedAt)}</div>}
        {active && task.status !== "running" && Number.isFinite(scheduled) && <div className="text-blue-300">{scheduled > now ? `距执行 ${duration(scheduled - now)}` : "已到执行时间，等待队列启动"}</div>}
        {Number.isFinite(started) && (Number.isFinite(completed) || task.status === "running") && <div className="text-zinc-200">{task.status === "running" ? "已执行" : "执行耗时"} · {duration((Number.isFinite(completed) ? completed : now) - started)}</div>}
    </div>
}
