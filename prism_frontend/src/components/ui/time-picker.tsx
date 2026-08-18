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

    const optionStyle = { backgroundColor: "#0a0a0a", color: "#ffffff" }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    className={cn(
                        "justify-start gap-2 rounded-2xl border-white/10 /50 text-left font-normal text-white hover:bg-white/5",
                        !value && "text-white/60",
                        className
                    )}
                >
                    <Clock className="h-4 w-4" />
                    {displayValue}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto border-white/10 bg-neutral-950 text-white p-4 shadow-2xl" align="start">
                <div className="space-y-4">
                    <div className="text-sm font-medium text-white">选择时间</div>
                    <div className="flex items-center gap-2">
                        {/* Hours */}
                        <div className="flex flex-col">
                            <label className="text-xs text-white/60 mb-1">时</label>
                            <select
                                value={hours}
                                onChange={(e) => setHours(e.target.value)}
                                className="appearance-none bg-neutral-900 text-white border border-white/10 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/60"
                                style={{ backgroundColor: "#0a0a0a", color: "#ffffff" }}
                            >
                                {Array.from({ length: 24 }, (_, i) => (
                                    <option
                                        key={i}
                                        value={String(i).padStart(2, "0")}
                                        style={optionStyle}
                                    >
                                        {String(i).padStart(2, "0")}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <span className="text-white/60 mt-6">:</span>
                        {/* Minutes */}
                        <div className="flex flex-col">
                            <label className="text-xs text-white/60 mb-1">分</label>
                            <select
                                value={minutes}
                                onChange={(e) => setMinutes(e.target.value)}
                                className="appearance-none bg-neutral-900 text-white border border-white/10 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/60"
                                style={{ backgroundColor: "#0a0a0a", color: "#ffffff" }}
                            >
                                {Array.from({ length: 60 }, (_, i) => (
                                    <option
                                        key={i}
                                        value={String(i).padStart(2, "0")}
                                        style={optionStyle}
                                    >
                                        {String(i).padStart(2, "0")}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <Button
                            variant="ghost"
                            className="flex-1 rounded-xl border border-white/10"
                            onClick={() => setOpen(false)}
                        >
                            取消
                        </Button>
                        <Button
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
