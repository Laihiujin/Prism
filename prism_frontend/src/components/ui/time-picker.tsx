"use client"

import { useState } from "react"
import { Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

interface TimePickerProps {
    value?: string // HH:mm format
    onChange: (time: string) => void
    className?: string
}

export function TimePicker({ value, onChange, className }: TimePickerProps) {
    const [open, setOpen] = useState(false)
    const [hours, setHours] = useState(value?.split(":")[0] || "10")
    const [minutes, setMinutes] = useState(value?.split(":")[1] || "00")

    const displayValue = value || "选择时间"

    const handleConfirm = () => {
        onChange(`${hours.padStart(2, "0")}:${minutes.padStart(2, "0")}`)
        setOpen(false)
    }

    const handleOpenChange = (nextOpen: boolean) => {
        if (nextOpen) {
            const [hour = "10", minute = "00"] = (value || "10:00").split(":")
            setHours(hour)
            setMinutes(minute)
        }
        setOpen(nextOpen)
    }

    return (
        <Popover open={open} onOpenChange={handleOpenChange}>
            <PopoverTrigger asChild>
                <Button
                    type="button"
                    variant="outline"
                    className={cn(
                        "justify-start gap-2 rounded-2xl border-border/70 /50 text-left font-normal text-foreground hover:bg-accent/40",
                        !value && "text-muted-foreground",
                        className
                    )}
                >
                    <Clock className="h-4 w-4" />
                    {displayValue}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-56 rounded-xl border-zinc-700 bg-zinc-950 text-foreground p-4 shadow-2xl" align="start" onFocusOutside={event => event.preventDefault()}>
                <div className="space-y-4">
                    <div className="text-sm font-medium text-foreground">选择时间</div>
                    <div className="grid grid-cols-2 gap-3">
                        {[{ label: "小时", count: 24, selected: hours, select: setHours }, { label: "分钟", count: 60, selected: minutes, select: setMinutes }].map(column => <div key={column.label} className="space-y-2">
                            <div className="text-xs text-zinc-400">{column.label} · {column.selected}</div>
                            <div role="group" aria-label={`选择${column.label}`} className="h-44 overflow-y-auto overscroll-contain rounded-lg border border-zinc-800 p-1">
                                {Array.from({ length: column.count }, (_, index) => {
                                    const option = String(index).padStart(2, "0")
                                    return <button key={option} type="button" aria-pressed={option === column.selected} ref={node => { if (node && option === column.selected) node.scrollIntoView({ block: "nearest" }) }} className={cn("block w-full rounded-md py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500", option === column.selected ? "bg-white text-black" : "text-zinc-400 hover:bg-zinc-800 hover:text-white")} onClick={() => column.select(option)}>{option}</button>
                                })}
                            </div>
                        </div>)}
                    </div>
                    <div className="flex gap-2">
                        <Button
                            type="button"
                            variant="ghost"
                            className="flex-1 rounded-xl border border-border/70"
                            onClick={() => setOpen(false)}
                        >
                            取消
                        </Button>
                        <Button
                            type="button"
                            className="flex-1 rounded-xl"
                            onClick={handleConfirm}
                        >
                            确认
                        </Button>
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    )
}
