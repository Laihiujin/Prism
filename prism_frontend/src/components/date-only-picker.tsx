"use client"

import { useEffect, useMemo, useState } from "react"
import { CalendarIcon } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

interface DateOnlyPickerProps {
  value?: Date
  onChange: (date?: Date) => void
  placeholder?: string
  label?: string
}

export function DateOnlyPicker({ value, onChange, placeholder = "选择日期", label = "定时日期" }: DateOnlyPickerProps) {
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState<Date | undefined>(value ?? new Date())
  const [tempDate, setTempDate] = useState<Date | undefined>(value)

  useEffect(() => {
    if (open) {
      setTempDate(value)
      setMonth(value ?? new Date())
    }
  }, [open, value])

  const displayValue = useMemo(() => {
    return value ? format(value, "yyyy-MM-dd") : placeholder
  }, [value, placeholder])

  const handleApply = () => {
    onChange(tempDate)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "justify-start gap-2 rounded-2xl border-white/20 bg-white/5 text-left font-normal",
            !value && "text-white/60"
          )}
        >
          <CalendarIcon className="h-4 w-4" />
          {displayValue}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-fit border-white/10 bg-background p-0">
        <Card className="border-white/10 bg-background">
          <CardHeader className="relative pb-2">
            <CardTitle>{label}</CardTitle>
            <CardDescription>选择定时日期</CardDescription>
            <Button
              size="sm"
              variant="outline"
              className="absolute right-4 top-4"
              onClick={() => {
                const today = new Date()
                setMonth(today)
                setTempDate(today)
              }}
            >
              今日
            </Button>
          </CardHeader>
          <CardContent className="pt-2">
            <Calendar
              mode="single"
              month={month}
              onMonthChange={setMonth}
              selected={tempDate}
              onSelect={setTempDate}
              className="bg-transparent p-0"
            />
            <div className="mt-4 flex gap-2">
              <Button variant="ghost" className="flex-1 rounded-2xl border border-white/10 bg-white/5" onClick={() => { onChange(undefined); setOpen(false) }}>
                清除
              </Button>
              <Button className="flex-1 rounded-2xl" onClick={handleApply} disabled={!tempDate}>
                确认
              </Button>
            </div>
          </CardContent>
        </Card>
      </PopoverContent>
    </Popover>
  )
}
