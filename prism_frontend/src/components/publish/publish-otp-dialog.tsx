"use client"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { backendBaseUrl } from "@/lib/env"
import { TaskVerifications } from "./task-verifications"

export function PublishOtpDialog() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const deferred = useRef(false)
  useEffect(() => {
    let cancelled = false
    let inFlight = false
    const poll = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const response = await fetch(`${backendBaseUrl}/api/v1/verification/otp-events`, { cache: "no-store" })
        if (!response.ok) return
        const payload = await response.json()
        if (cancelled) return
        const count = Array.isArray(payload.events) ? payload.events.length : 0
        setPendingCount(count)
        if (!count) { setOpen(false); deferred.current = false }
        else if (!deferred.current && !pathname.startsWith("/tasks")) setOpen(true)
      } catch {
        // Retry transient connection failures without discarding pending requests.
      } finally { inFlight = false }
    }
    void poll()
    const timer = setInterval(() => void poll(), 2000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [pathname])
  if (pathname.startsWith("/tasks")) return null
  const dismiss = () => { deferred.current = true; setOpen(false) }
  return <>
    {pendingCount > 0 && !open && <div className="fixed bottom-5 right-5 z-50 flex gap-2 rounded-lg border bg-background p-2">
      <Button onClick={() => setOpen(true)}>待验证任务（{pendingCount}）</Button>
      <Button variant="outline" asChild><Link href="/tasks/verification">人工验证</Link></Button>
    </div>}
    <Dialog open={open} onOpenChange={value => { if (value) setOpen(true); else dismiss() }}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border/70">
        <DialogHeader>
          <DialogTitle>发布身份验证 · {pendingCount} 个待处理</DialogTitle>
          <p className="text-sm text-muted-foreground">所有账号同时列出，可分别回传或重新获取验证码。关闭窗口后仍可在任务管理中处理，超过验证时限的任务需重试。</p>
          <Link href="/tasks/verification" className="text-sm underline" onClick={dismiss}>打开任务发布人工验证</Link>
        </DialogHeader>
        <TaskVerifications />
        <DialogFooter><Button variant="ghost" onClick={dismiss}>收起，稍后处理</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </>
}
