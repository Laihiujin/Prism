"use client"

import { useEffect, useRef, useState, type PointerEvent } from "react"
import { backendBaseUrl } from "@/lib/env"

type Position = { x: number; y: number }
type Frame = { image: string; width: number; height: number }

export function RemoteLoginView({ sessionId, openByDefault = false }: { sessionId: string; openByDefault?: boolean }) {
  const [open, setOpen] = useState(openByDefault)
  return <div className="w-full space-y-2">
    <button type="button" className="text-sm underline" onClick={() => setOpen(value => !value)}>{open ? "关闭远程验证画面" : "打开远程验证画面"}</button>
    {open && <BrowserViewport key={sessionId} sessionId={sessionId} />}
  </div>
}

function BrowserViewport({ sessionId }: { sessionId: string }) {
  const [frame, setFrame] = useState<Frame | null>(null)
  const [error, setError] = useState("")
  const [zoom, setZoom] = useState(false)
  const dragging = useRef(false)
  const latestMove = useRef<Position | null>(null)
  const queue = useRef(Promise.resolve())
  const failed = useRef(false)
  const moving = useRef(false)

  const send = (action: "down" | "move" | "up" | "cancel", position: Position) => {
    queue.current = queue.current.then(async () => {
      if (failed.current && action !== "cancel") return
      const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/pointer/${encodeURIComponent(sessionId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, ...position }),
      })
      if (!response.ok) throw new Error("操作未成功，请松开鼠标并重新打开验证画面。")
    }).catch(() => { failed.current = true; dragging.current = false; setError("连接中断，请重新打开验证画面后重试。") })
    return queue.current
  }

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const controller = new AbortController()
    const refresh = async () => {
      try {
        const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/view/${encodeURIComponent(sessionId)}`, { signal: controller.signal, cache: "no-store" })
        if (!response.ok) throw new Error("登录会话已结束或画面暂不可用，请重新开始登录。")
        const next = await response.json() as Frame
        if (!cancelled) setFrame(next)
      } catch (problem) {
        if (!cancelled) setError(problem instanceof Error ? problem.message : "画面连接失败")
      } finally {
        if (!cancelled) timer = setTimeout(refresh, 750)
      }
    }
    void refresh()
    return () => {
      cancelled = true; controller.abort(); clearTimeout(timer)
      if (dragging.current) {
        void fetch(`${backendBaseUrl}/api/v1/auth/qrcode/pointer/${encodeURIComponent(sessionId)}`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "cancel", x: 0, y: 0 }), keepalive: true,
        }).catch(() => {})
      }
    }
  }, [sessionId])

  const position = (event: PointerEvent<HTMLImageElement>): Position => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }
  }
  const flushMove = () => {
    if (!moving.current && latestMove.current && dragging.current) {
      moving.current = true
      const next = latestMove.current; latestMove.current = null
      void send("move", next).finally(() => { moving.current = false; flushMove() })
    }
  }

  return <div className="w-full space-y-2 rounded-xl border border-border p-3">
    <p className="text-sm font-semibold">远程手动验证</p>
    <p className="text-xs text-muted-foreground">在画面上点击或拖动即可操作当前登录浏览器。安全验证需由你手动完成。</p>
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    <button type="button" className="text-xs underline" onClick={() => setZoom(value => !value)}>{zoom ? "恢复大小" : "放大画面"}</button>
    {frame ? <div className="max-h-[60vh] overflow-auto"><img src={frame.image} alt="当前平台登录浏览器实时画面" draggable={false}
      className="max-w-none select-none touch-none rounded border border-border"
      style={{ width: zoom ? "200%" : "100%", aspectRatio: `${frame.width}/${frame.height}` }}
      onPointerDown={event => { if (event.button !== 0 || dragging.current || failed.current) return; dragging.current = true; event.currentTarget.setPointerCapture(event.pointerId); send("down", position(event)) }}
      onPointerMove={event => { if (!dragging.current) return; latestMove.current = position(event); flushMove() }}
      onPointerUp={event => { if (!dragging.current) return; latestMove.current = null; send("up", position(event)); dragging.current = false; event.currentTarget.releasePointerCapture(event.pointerId) }}
      onPointerCancel={event => { latestMove.current = null; send("cancel", position(event)); dragging.current = false }}
    /></div> : <p role="status" className="text-xs">正在连接浏览器画面…</p>}
  </div>
}
