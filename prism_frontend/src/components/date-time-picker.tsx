"use client"

import { useEffect, useMemo, useState } from "react"
import { CalendarIcon, Clock2Icon } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

interface DateTimePickerProps {
  label: string
  value?: Date
  onChange: (date?: Date) => void
  placeholder?: string
  className?: string
}

export function DateTimePicker({
  label,
  value,
  onChange,
  placeholder = "选择时间",
  className,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false)
  const [tempDate, setTempDate] = useState<Date | undefined>(value ?? new Date())
  const [tempTime, setTempTime] = useState(() => (value ? format(value, "HH:mm") : "10:00"))

  useEffect(() => {
    if (open) {
      setTempDate(value ?? new Date())
      setTempTime(value ? format(value, "HH:mm") : format(new Date(), "HH:mm"))
    }
  }, [open, value])

  const displayValue = useMemo(() => {
    if (!value) return placeholder
    return format(value, "yyyy-MM-dd HH:mm")
  }, [value, placeholder])

  const applySelection = () => {
    if (!tempDate) {
      onChange(undefined)
      setOpen(false)
      return
    }
    const [hourString = "00", minuteString = "00"] = tempTime.split(":")
    const merged = new Date(tempDate)
    merged.setHours(Number(hourString), Number(minuteString), 0, 0)
    onChange(merged)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "justify-start gap-2 rounded-2xl border-white/20 bg-white/5 text-left font-normal",
            !value && "text-white/60",
            className
          )}
        >
          <CalendarIcon className="h-4 w-4" />
          {displayValue}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-fit border-white/10 bg-background p-0" align="start">
        <Card className="w-fit border-white/10 bg-background">
          <CardContent className="px-4 pt-4">
            <Calendar
              mode="single"
              selected={tempDate}
              onSelect={setTempDate}
              className="bg-transparent p-0"
            />
          </CardContent>
          <CardFooter className="flex flex-col gap-3 border-t border-white/10 px-4 py-4">
            <div className="flex w-full flex-col gap-2">
              <Label htmlFor={`${label}-time`} className="text-sm text-white/70">
                {label}时间
              </Label>
              <div className="relative">
                <Clock2Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/50" />
                <Input
                  id={`${label}-time`}
                  type="time"
                  value={tempTime}
                  onChange={(event) => setTempTime(event.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <div className="flex w-full gap-2">
              <Button
                type="button"
                variant="ghost"
                className="flex-1 rounded-2xl border border-white/10 bg-white/5"
                onClick={() => {
                  onChange(undefined)
                  setOpen(false)
                }}
              >
                清除
              </Button>
              <Button type="button" className="flex-1 rounded-2xl" onClick={applySelection} disabled={!tempDate}>
                确认
              </Button>
            </div>
          </CardFooter>
        </Card>
      </PopoverContent>
    </Popover>
  )
}
