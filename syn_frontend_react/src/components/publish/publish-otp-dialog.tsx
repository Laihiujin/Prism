"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from "@/components/ui/input-otp"

type OtpEvent = {
  id: string
  platform?: number
  account?: string
  message?: string
}

export function PublishOtpDialog() {
  const [open, setOpen] = useState(false)
  const [event, setEvent] = useState<OtpEvent | null>(null)
  const [code, setCode] = useState("")
  const [submitting, setSubmitting] = useState(false)

  /*
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/v1/verification/otp-events", { cache: "no-store" })
        const payload = await res.json().catch(() => ({}))
        const rows: OtpEvent[] = Array.isArray(payload?.events) ? payload.events : []
        if (rows.length) {
          setEvent(rows[0])
          setOpen(true)
          setCode("")
        }
      } catch (error) {
        console.error("Failed to poll otp events", error)
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [])
  */

  const handleSubmit = async () => {
    if (!event?.id || code.length !== 6) return
    setSubmitting(true)
    try {
      const res = await fetch("/api/v1/verification/submit-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: event.id, code }),
      })
      if (res.ok) {
        setOpen(false)
        setEvent(null)
        setCode("")
      }
    } catch (error) {
      console.error("Failed to submit otp", error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className=" border-white/10 max-w-md">
        <DialogHeader>
          <DialogTitle>短信验证</DialogTitle>
          <p className="text-sm text-white/60">
            {event?.message || "发布需要短信验证，请输入 6 位验证码"}
          </p>
        </DialogHeader>
        <div className="flex flex-col items-center gap-4 py-4">
          <InputOTP maxLength={6} value={code} onChange={setCode}>
            <InputOTPGroup>
              <InputOTPSlot index={0} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
              <InputOTPSlot index={1} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
              <InputOTPSlot index={2} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
            </InputOTPGroup>
            <InputOTPSeparator />
            <InputOTPGroup>
              <InputOTPSlot index={3} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
              <InputOTPSlot index={4} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
              <InputOTPSlot index={5} className="h-12 w-10 rounded-xl border-white/10 bg-neutral-900 text-white" />
            </InputOTPGroup>
          </InputOTP>
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
