"use client"

import * as React from "react"
import { parseDate } from "chrono-node"
import { CalendarIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"

function formatDate(date: Date | undefined) {
    if (!date) {
        return ""
    }

    return date.toLocaleDateString("zh-CN", {
        day: "2-digit",
        month: "long",
        year: "numeric",
    })
}

interface NaturalDatePickerProps {
    value: string
    onChange: (value: string) => void
    label?: string
    placeholder?: string
}

export function NaturalDatePicker({ value, onChange, label = "过期时间", placeholder = "明天 或 下周" }: NaturalDatePickerProps) {
    const [open, setOpen] = React.useState(false)
    const [date, setDate] = React.useState<Date | undefined>(
        parseDate(value) || undefined
    )
    const [month, setMonth] = React.useState<Date | undefined>(date)

    return (
        <div className="flex flex-col gap-2">
            <Label htmlFor="date" className="text-xs text-muted-foreground">
                {label}
            </Label>
            <div className="relative flex gap-2">
                <Input
                    id="date"
                    value={value}
                    placeholder={placeholder}
                    className="/50 border-border/70 text-foreground pr-10 rounded-2xl"
                    onChange={(e) => {
                        onChange(e.target.value)
                        const parsedDate = parseDate(e.target.value)
                        if (parsedDate) {
                            setDate(parsedDate)
                            setMonth(parsedDate)
                        }
                    }}
                    onKeyDown={(e) => {
                        if (e.key === "ArrowDown") {
                            e.preventDefault()
                            setOpen(true)
                        }
                    }}
                />
                <Popover open={open} onOpenChange={setOpen}>
                    <PopoverTrigger asChild>
                        <Button
                            id="date-picker"
                            variant="ghost"
                            className="absolute top-1/2 right-2 size-6 -translate-y-1/2 rounded-xl"
                        >
                            <CalendarIcon className="size-3.5" />
                            <span className="sr-only">选择日期</span>
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto overflow-hidden p-0 border-border/70 bg-card" align="end">
                        <Calendar
                            mode="single"
                            selected={date}
                            captionLayout="dropdown"
                            month={month}
                            onMonthChange={setMonth}
                            onSelect={(selectedDate) => {
                                setDate(selectedDate)
                                onChange(formatDate(selectedDate))
                                setOpen(false)
                            }}
                            className="rounded-2xl"
                        />
                    </PopoverContent>
                </Popover>
            </div>
            {date && (
                <div className="text-muted-foreground px-1 text-xs">
                    任务将在 <span className="font-medium text-foreground">{formatDate(date)}</span> 过期
                </div>
            )}
        </div>
    )
}
