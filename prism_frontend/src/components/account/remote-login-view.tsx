"use client"

import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react"
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

export function BrowserViewport({ sessionId }: { sessionId: string }) {
  const [frame, setFrame] = useState<Frame | null>(null)
  const [error, setError] = useState("")
  const [text, setText] = useState("")
  const [zoom, setZoom] = useState(false)
  const [pan, setPan] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const dragging = useRef(false)
  const latestMove = useRef<Position | null>(null)
  const queue = useRef(Promise.resolve())
  const failed = useRef(false)
  const moving = useRef(false)

  const send = useCallback((action: "down" | "move" | "up" | "cancel" | "wheel" | "text" | "key", position: Partial<Position> & { delta_x?: number; delta_y?: number; text?: string; key?: string }) => {
    queue.current = queue.current.then(async () => {
      if (failed.current && action !== "cancel") return
      const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/pointer/${encodeURIComponent(sessionId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, ...position }),
      })
      if (!response.ok) throw new Error("操作未成功，请松开鼠标并重新打开验证画面。")
    }).catch(() => { failed.current = true; dragging.current = false; setError("连接中断，请重新打开验证画面后重试。") })
    return queue.current
  }, [sessionId])

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const controller = new AbortController()
    const refresh = async () => {
      try {
        const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/view/${encodeURIComponent(sessionId)}`, { signal: controller.signal, cache: "no-store" })
        if (!response.ok) throw new Error("浏览器会话已结束或画面暂不可用，请重新打开创作者中心或开始登录。")
        const next = await response.json() as Frame
        if (!cancelled) { setFrame(next); if (!failed.current) setError("") }
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

  const hasFrame = frame !== null
  useEffect(() => {
    const element = viewport.current
    if (!element || pan) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight : 1
      void send("wheel", { delta_x: Math.max(-2000, Math.min(2000, event.deltaX * scale)), delta_y: Math.max(-2000, Math.min(2000, event.deltaY * scale)) })
    }
    element.addEventListener("wheel", onWheel, { passive: false })
    return () => element.removeEventListener("wheel", onWheel)
  }, [pan, hasFrame, send])

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
    <p className="text-sm font-semibold">远程浏览器实时画面</p>
    <p className="text-xs text-muted-foreground">点击、拖动、滚轮和键盘均可操作网页。中文或多行文字可在下方输入后发送。</p>
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    <button type="button" className="text-xs underline" onClick={() => { setZoom(value => !value); setPan(!zoom) }}>{zoom ? "恢复大小" : "放大画面"}</button>
    {zoom && <button type="button" className="ml-4 text-xs underline" onClick={() => setPan(value => !value)}>{pan ? "切换为操作网页" : "切换为移动画面"}</button>}
    {zoom && <p className="text-xs text-muted-foreground">{pan ? "拖动画面可查看放大后的任意位置；需要点击网页时切换为操作网页。" : "当前手势会操作远程网页。"}</p>}
    <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); if (text) void send("text", { text }).then(() => { if (!failed.current) setText("") }) }}>
      <textarea rows={2} aria-label="输入到远程网页" className="min-w-0 flex-1 rounded border border-border bg-background px-3 py-2 text-sm" value={text} maxLength={4000} onChange={event => setText(event.target.value)} placeholder="先点击网页输入框，再输入文字" />
      <button className="rounded border border-border px-3 text-sm" disabled={!text}>发送文字</button>
      {(["Tab", "Enter", "Backspace", "Escape"] as const).map(key => <button key={key} type="button" className="rounded border border-border px-2 text-xs" onClick={() => void send("key", { key })}>{key}</button>)}
      <button type="button" className="rounded border border-border px-2 text-xs" onClick={() => void send("wheel", { delta_y: -500 })}>向上滚动</button>
      <button type="button" className="rounded border border-border px-2 text-xs" onClick={() => void send("wheel", { delta_y: 500 })}>向下滚动</button>
    </form>
    {frame ? <div ref={viewport} tabIndex={0} role="region" aria-label="远程网页操作区域，点击后可用键盘操作"
      onKeyDown={event => {
        if (pan || event.nativeEvent.isComposing) return
        const special = ["Enter", "Tab", "Backspace", "Delete", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]
        if (event.key.length !== 1 && !special.includes(event.key)) return
        if (event.key.length === 1 && (event.ctrlKey || event.metaKey || event.altKey) && !/^[a-zA-Z0-9 ]$/.test(event.key)) return
        event.preventDefault()
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) { void send("text", { text: event.key }); return }
        const key = [event.ctrlKey && "Control", event.metaKey && "Meta", event.altKey && "Alt", event.shiftKey && "Shift", event.key === " " ? "Space" : event.key].filter(Boolean).join("+")
        void send("key", { key })
      }}
 className="max-h-[60vh] w-full min-w-0 overflow-auto"><img src={frame.image} alt="当前平台浏览器实时画面" draggable={false}
      className="max-w-none select-none touch-none rounded border border-border"
      style={{ width: zoom ? "200%" : "100%", aspectRatio: `${frame.width}/${frame.height}` }}
      onPointerDown={event => {
        if (event.button !== 0) return
        viewport.current?.focus({ preventScroll: true })
        if (pan && viewport.current) { panStart.current = { x: event.clientX, y: event.clientY, left: viewport.current.scrollLeft, top: viewport.current.scrollTop }; event.currentTarget.setPointerCapture(event.pointerId); return }
        if (dragging.current || failed.current) return; dragging.current = true; event.currentTarget.setPointerCapture(event.pointerId); send("down", position(event))
      }}
      onPointerMove={event => {
        if (panStart.current && viewport.current) { viewport.current.scrollLeft = panStart.current.left + panStart.current.x - event.clientX; viewport.current.scrollTop = panStart.current.top + panStart.current.y - event.clientY; return }
        if (!dragging.current) return; latestMove.current = position(event); flushMove()
      }}
      onPointerUp={event => { if (panStart.current) { panStart.current = null; event.currentTarget.releasePointerCapture(event.pointerId); return }; if (!dragging.current) return; latestMove.current = null; send("up", position(event)); dragging.current = false; event.currentTarget.releasePointerCapture(event.pointerId) }}
      onPointerCancel={event => { if (panStart.current) { panStart.current = null; return }; latestMove.current = null; send("cancel", position(event)); dragging.current = false }}
    /></div> : <p role="status" className="text-xs">正在连接浏览器画面…</p>}
  </div>
}
