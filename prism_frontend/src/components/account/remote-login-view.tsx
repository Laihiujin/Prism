"use client"

import { useEffect, useRef, useState, type PointerEvent } from "react"
import { backendBaseUrl } from "@/lib/env"

type Position = { x: number; y: number }
type FocusBox = Position & { width: number; height: number }
type Frame = { image: string; width: number; height: number; focus?: FocusBox | null }
type BrowserInput = { action: "type"; text: string } | { action: "key"; key: string } | ({ action: "down" | "move" | "up" | "cancel" } & Position)

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
  const [zoom, setZoom] = useState(false)
  const [pan, setPan] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)
  const panStart = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const dragging = useRef(false)
  const latestMove = useRef<Position | null>(null)
  const queue = useRef(Promise.resolve())
  const failed = useRef(false)
  const moving = useRef(false)
  const composing = useRef(false)
  const focusMarker = useRef<HTMLDivElement>(null)
  const focusKey = frame?.focus ? JSON.stringify(frame.focus) + zoom : ""

  useEffect(() => {
    if (focusKey) focusMarker.current?.scrollIntoView({ block: "nearest", inline: "nearest" })
  }, [focusKey])

  const sendInput = (input: BrowserInput) => {
    queue.current = queue.current.then(async () => {
      if (failed.current && input.action !== "cancel") return
      const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/pointer/${encodeURIComponent(sessionId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
      })
      if (!response.ok) throw new Error("操作未成功，请松开鼠标并重新打开验证画面。")
    }).catch(() => { failed.current = true; dragging.current = false; setError("连接中断，请重新打开验证画面后重试。") })
    return queue.current
  }
  const send = (action: "down" | "move" | "up" | "cancel", position: Position) => sendInput({ action, ...position })

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const controller = new AbortController()
    const refresh = async () => {
      try {
        const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/view/${encodeURIComponent(sessionId)}`, { signal: controller.signal, cache: "no-store" })
        if (!response.ok) throw new Error("浏览器会话已结束或画面暂不可用，请重新打开创作者中心或开始登录。")
        const next = await response.json() as Frame
        if (!cancelled) { setFrame(next); setError("") }
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
    <p className="text-sm font-semibold">远程浏览器实时画面</p>
    <p className="text-xs text-muted-foreground">点击网页输入框后，可在下方输入或粘贴文字。蓝框标出网页当前聚焦的输入框。安全验证需由你手动完成。</p>
    <textarea aria-label="向远程浏览器输入文字" rows={1} placeholder="先点击网页输入框，再在这里输入或粘贴"
      className="w-full rounded border border-border bg-transparent p-2 text-sm"
      onCompositionStart={() => { composing.current = true }}
      onCompositionEnd={event => { composing.current = false; const text = event.currentTarget.value; event.currentTarget.value = ""; if (text) void sendInput({ action: "type", text }) }}
      onChange={event => { if (composing.current) return; const text = event.currentTarget.value; event.currentTarget.value = ""; if (text) void sendInput({ action: "type", text }) }}
      onPaste={event => { event.preventDefault(); const text = event.clipboardData.getData("text/plain"); if (text) void sendInput({ action: "type", text }) }}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing || composing.current || event.key === "Process") return
        const special = /^(Backspace|Delete|Enter|Tab|Escape|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End|PageUp|PageDown)$/.test(event.key)
        const shortcut = (event.ctrlKey || event.metaKey) && /^[aAzZyY]$/.test(event.key)
        if (!special && !shortcut) return
        event.preventDefault()
        const key = [event.ctrlKey && "Control", event.metaKey && "Meta", event.altKey && "Alt", event.shiftKey && "Shift", event.key].filter(Boolean).join("+")
        void sendInput({ action: "key", key })
      }} />
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    <button type="button" className="text-xs underline" onClick={() => { setZoom(value => !value); setPan(!zoom) }}>{zoom ? "恢复大小" : "放大画面"}</button>
    {zoom && <button type="button" className="ml-4 text-xs underline" onClick={() => setPan(value => !value)}>{pan ? "切换为操作网页" : "切换为移动画面"}</button>}
    {zoom && <p className="text-xs text-muted-foreground">{pan ? "拖动画面可查看放大后的任意位置；需要点击网页时切换为操作网页。" : "当前手势会操作远程网页。"}</p>}
    {frame ? <div ref={viewport} className="max-h-[60vh] w-full min-w-0 overflow-auto"><div className="relative" style={{ width: zoom ? "200%" : "100%" }}><img src={frame.image} alt="当前平台浏览器实时画面" draggable={false} tabIndex={0}
      onPaste={event => { event.preventDefault(); const text = event.clipboardData.getData("text/plain"); if (text) void sendInput({ action: "type", text }) }}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          event.preventDefault(); void sendInput({ action: "type", text: event.key }); return
        }
        if (!/^(Backspace|Delete|Enter|Tab|Escape|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End|PageUp|PageDown)$/.test(event.key) && !((event.ctrlKey || event.metaKey) && /^[aAzZyY]$/.test(event.key))) return
        event.preventDefault()
        void sendInput({ action: "key", key: [event.ctrlKey && "Control", event.metaKey && "Meta", event.altKey && "Alt", event.shiftKey && "Shift", event.key].filter(Boolean).join("+") })
      }}
      className="max-w-none select-none touch-none rounded border border-border"
      style={{ width: "100%", aspectRatio: `${frame.width}/${frame.height}` }}
      onPointerDown={event => {
        if (event.button !== 0) return
        event.currentTarget.focus({ preventScroll: true })
        if (pan && viewport.current) { panStart.current = { x: event.clientX, y: event.clientY, left: viewport.current.scrollLeft, top: viewport.current.scrollTop }; event.currentTarget.setPointerCapture(event.pointerId); return }
        if (dragging.current || failed.current) return; dragging.current = true; event.currentTarget.setPointerCapture(event.pointerId); send("down", position(event))
      }}
      onPointerMove={event => {
        if (panStart.current && viewport.current) { viewport.current.scrollLeft = panStart.current.left + panStart.current.x - event.clientX; viewport.current.scrollTop = panStart.current.top + panStart.current.y - event.clientY; return }
        if (!dragging.current) return; latestMove.current = position(event); flushMove()
      }}
      onPointerUp={event => { if (panStart.current) { panStart.current = null; event.currentTarget.releasePointerCapture(event.pointerId); return }; if (!dragging.current) return; latestMove.current = null; send("up", position(event)); dragging.current = false; event.currentTarget.releasePointerCapture(event.pointerId) }}
      onPointerCancel={event => { if (panStart.current) { panStart.current = null; return }; latestMove.current = null; send("cancel", position(event)); dragging.current = false }}
    />{frame.focus && <div ref={focusMarker} aria-label="网页当前输入位置" className="pointer-events-none absolute rounded outline outline-2 outline-blue-500"
      style={{ left: `${100 * frame.focus.x / frame.width}%`, top: `${100 * frame.focus.y / frame.height}%`, width: `${100 * frame.focus.width / frame.width}%`, height: `${100 * frame.focus.height / frame.height}%` }} />}</div></div> : <p role="status" className="text-xs">正在连接浏览器画面…</p>}
  </div>
}
