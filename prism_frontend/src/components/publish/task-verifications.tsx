"use client"

import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { platformLabel } from "@/lib/platform-label"

type Verification = { id: string; task_id?: string; account?: string; platform?: number; message?: string; code_length?: number; expires_at?: number; can_resend?: boolean }

export function TaskVerifications({ showEmpty = false }: { showEmpty?: boolean }) {
  const client = useQueryClient()
  const [codes, setCodes] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string[]>([])
  const { data: events = [], isError, isPending, refetch } = useQuery<Verification[]>({
    queryKey: ["publish-verifications"],
    queryFn: async () => {
      const response = await fetch("/api/publish/otp-events", { cache: "no-store" })
      if (!response.ok) throw new Error("验证状态读取失败")
      const payload = await response.json()
      return Array.isArray(payload.events) ? payload.events : []
    },
    refetchInterval: 2000,
  })
  async function submit(event: Verification) {
    setBusy(previous => [...previous, event.id])
    setErrors(previous => ({ ...previous, [event.id]: "" }))
    try {
      const response = await fetch("/api/publish/submit-code", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: event.id, code: codes[event.id] }),
      })
      if (!response.ok) throw new Error("验证码回传失败或请求已过期，请重试。")
      setCodes(previous => ({ ...previous, [event.id]: "" }))
      await client.invalidateQueries({ queryKey: ["publish-verifications"] })
      await client.invalidateQueries({ queryKey: ["tasks"] })
    } catch (error) {
      setErrors(previous => ({ ...previous, [event.id]: error instanceof Error ? error.message : "回传失败" }))
    } finally { setBusy(previous => previous.filter(id => id !== event.id)) }
  }
  async function resend(event: Verification) {
    setBusy(previous => [...previous, event.id])
    try {
      const response = await fetch("/api/publish/resend-code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: event.id }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || "重新获取失败")
      setErrors(previous => ({ ...previous, [event.id]: "已通知该任务的发布浏览器重新获取，请查看手机短信；平台可能仍在冷却中。" }))
    } catch (error) { setErrors(previous => ({ ...previous, [event.id]: error instanceof Error ? error.message : "重新获取失败" })) }
    finally { setBusy(previous => previous.filter(id => id !== event.id)) }
  }
  if (!events.length && !isError && !showEmpty) return null
  return <section aria-label="发布任务身份验证" className="space-y-3 rounded-xl border border-zinc-600 p-4">
    <h2 className="font-semibold">发布任务等待验证（{events.length}）</h2>
    {showEmpty && <Button variant="outline" onClick={() => void refetch()}>刷新验证请求</Button>}
    {showEmpty && isPending && <p className="text-sm text-muted-foreground">正在加载验证请求…</p>}
    {showEmpty && !isPending && !isError && !events.length && <p className="text-sm text-muted-foreground">暂无等待回传的验证码。发布触发验证后，对应平台、账号和任务会自动出现在这里；已过期或失败的任务请回到任务管理重试。</p>}
    {isError && <p role="alert" className="text-sm text-destructive">暂时无法读取验证请求，正在重试。</p>}
    {events.map(event => <div key={event.id} className="space-y-2 rounded-lg border border-zinc-600 p-3">
      <p className="text-sm font-medium">{platformLabel(event.platform || 0)} · {event.account || "发布账号"}</p>
      {event.task_id && <p className="break-all text-xs text-muted-foreground">任务：{event.task_id}</p>}
      <p className="text-sm">{event.message || "请输入手机收到的验证码"}</p>
      <div className="flex items-center gap-2">
        <Input aria-label={`${event.task_id || event.id} 验证码`} inputMode="numeric" autoComplete="one-time-code" placeholder={`请输入 ${event.code_length || 6} 位验证码`} maxLength={event.code_length || 6} value={codes[event.id] || ""} onChange={e => setCodes(previous => ({ ...previous, [event.id]: e.target.value.replace(/[^0-9]/g, "") }))} />
        <Button type="button" variant="outline" disabled={busy.includes(event.id) || (codes[event.id] || "").length !== (event.code_length || 6)} onClick={() => void submit(event)}>{busy.includes(event.id) ? "回传中…" : "回传验证码"}</Button>
      </div>
      {event.can_resend && <Button variant="outline" disabled={busy.includes(event.id)} onClick={() => void resend(event)}>重新获取验证码</Button>}
      {event.expires_at && <p className="text-xs text-muted-foreground">请求过期时间：{new Date(event.expires_at * 1000).toLocaleTimeString("zh-CN")}</p>}
      {errors[event.id] && <p role="alert" className="text-sm text-destructive">{errors[event.id]}</p>}
      <p className="text-xs text-muted-foreground">回传后由平台确认，验证通过后发布任务继续执行。</p>
    </div>)}
  </section>
}
