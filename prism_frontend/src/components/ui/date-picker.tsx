"use client"

import { useState } from "react"
import { CalendarIcon } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

interface DatePickerProps {
    value?: string // YYYY-MM-DD format
    onChange: (date?: string) => void
    placeholder?: string
    className?: string
}

export function DatePicker({
    value,
    onChange,
    placeholder = "选择日期",
    className,
}: DatePickerProps) {
    const [open, setOpen] = useState(false)

    const selectedDate = value ? new Date(value) : undefined

    const displayValue = value
        ? format(new Date(value), "yyyy年MM月dd日")
        : placeholder

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    className={cn(
                        "justify-start gap-2 rounded-2xl border-border/70 text-left font-normal text-foreground hover:bg-accent/40",
                        !value && "text-muted-foreground",
                        className
                    )}
                >
                    <CalendarIcon className="h-4 w-4" />
                    {displayValue}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto border-border/70 bg-card p-0" align="start">
                <Calendar
                    mode="single"
                    selected={selectedDate}
                    onSelect={(date) => {
                        if (date) {
                            onChange(format(date, "yyyy-MM-dd"))
                        } else {
                            onChange(undefined)
                        }
                        setOpen(false)
                    }}
                    className="bg-transparent rounded-2xl"
                    initialFocus
                />
            </PopoverContent>
        </Popover>
    )
}
