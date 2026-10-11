"use client"

import { useEffect, useRef, useState } from "react"
import { usePathname } from "next/navigation"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from "@/components/ui/input-otp"
import { backendBaseUrl } from "@/lib/env"

type OtpEvent = {
  id: string
  platform?: number
  account?: string
  message?: string
}

export function PublishOtpDialog() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [event, setEvent] = useState<OtpEvent | null>(null)
  const [code, setCode] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const accepted = useRef(new Set<string>())
  const currentEventId = useRef<string | null>(null)

  useEffect(() => {
    if (pathname === "/tasks") return
    let cancelled = false
    let inFlight = false
    const poll = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const res = await fetch(`${backendBaseUrl}/api/v1/verification/otp-events`, { cache: "no-store" })
        if (!res.ok || cancelled) return
        const payload = await res.json().catch(() => ({}))
        const rows: OtpEvent[] = Array.isArray(payload?.events) ? payload.events : []
        const next = rows.find(row => !accepted.current.has(row.id))
        if (next && !cancelled) {
          if (currentEventId.current !== next.id) {
            currentEventId.current = next.id
            setCode("")
            setError("")
          }
          setEvent(current => current?.id === next.id ? current : next)
          setOpen(true)
        }
      } catch {
        // Transient connection failures are retried by the next poll.
      } finally {
        inFlight = false
      }
    }
    void poll()
    const timer = setInterval(() => void poll(), 2000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [pathname])

  const handleSubmit = async () => {
    if (!event?.id || code.length !== 6) return
    setSubmitting(true)
    setError("")
    try {
      const res = await fetch(`${backendBaseUrl}/api/v1/verification/submit-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: event.id, code }),
      })
      if (res.ok) {
        accepted.current.add(event.id)
        setOpen(false)
        setEvent(null)
        setCode("")
      } else {
        setError("验证码回传失败，请检查请求是否已过期后重试")
      }
    } catch {
      setError("无法连接验证码服务，请重试")
    } finally {
      setSubmitting(false)
    }
  }

  if (pathname === "/tasks") return null

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className=" border-border/70 max-w-md">
        <DialogHeader>
          <DialogTitle>短信验证</DialogTitle>
          <p className="text-sm text-muted-foreground">
            {event?.message || "发布需要短信验证，请输入 6 位验证码"}
          </p>
        </DialogHeader>
        <div className="flex flex-col items-center gap-4 py-4">
          <InputOTP maxLength={6} value={code} onChange={setCode}>
            <InputOTPGroup>
              <InputOTPSlot index={0} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
              <InputOTPSlot index={1} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
              <InputOTPSlot index={2} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
            </InputOTPGroup>
            <InputOTPSeparator />
            <InputOTPGroup>
              <InputOTPSlot index={3} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
              <InputOTPSlot index={4} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
              <InputOTPSlot index={5} className="h-12 w-10 rounded-xl border-border/70 bg-black text-foreground" />
            </InputOTPGroup>
          </InputOTP>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="ghost" className="rounded-xl" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button className="rounded-xl" disabled={code.length !== 6 || submitting} onClick={handleSubmit}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                提交中...
              </>
            ) : (
              "提交验证码"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
