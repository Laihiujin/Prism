"use client"

import { useEffect, useRef, useState } from "react"
import jsQR from "jsqr"
import { backendBaseUrl } from "@/lib/env"

type QrArea = { x: number; y: number; width: number; height: number }

export function LoginIdentityQr({ sessionId }: { sessionId: string }) {
  const [image, setImage] = useState("")
  const [message, setMessage] = useState("正在读取原设备扫码二维码…")
  const [busy, setBusy] = useState(false)
  const area = useRef<QrArea | null>(null)
  const refreshing = useRef(false)
  const lastQrAt = useRef(Date.now())
  const firstQrAt = useRef(Date.now())
  const attempts = useRef(0)
  const cancelled = useRef(false)

  const refresh = async () => {
    if (refreshing.current) return
    refreshing.current = true; setBusy(true)
    try {
      const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/sms`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, action: "identity_qr" }),
      })
      if (!response.ok) {
        // Existing workers can keep their live session: click only the known QR
        // refresh area, without closing or recreating the login browser.
        if (!area.current || ![409, 422].includes(response.status)) throw new Error()
        const position = { x: area.current.x + area.current.width / 2, y: area.current.y + area.current.height / 2 }
        for (const action of ["down", "up"]) {
          const pointer = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/pointer/${encodeURIComponent(sessionId)}`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, ...position }),
          })
          if (!pointer.ok) throw new Error()
        }
      }
      setMessage("正在刷新二维码…")
      firstQrAt.current = Date.now(); attempts.current += 1
    } catch { setMessage("二维码刷新失败，请点击重新刷新。") }
    finally { refreshing.current = false; setBusy(false) }
  }

  useEffect(() => {
    cancelled.current = false
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    let previousImage = ""
    const poll = async () => {
      try {
        const response = await fetch(`${backendBaseUrl}/api/v1/auth/qrcode/view/${encodeURIComponent(sessionId)}`, { signal: controller.signal, cache: "no-store" })
        if (!response.ok) { if (!cancelled.current) setMessage("登录会话已结束，请查看账号绑定结果。"); return }
        const frame = await response.json()
        const source = new Image(); source.src = frame.image
        await source.decode()
        if (cancelled.current) return
        const canvas = document.createElement("canvas"); canvas.width = source.naturalWidth; canvas.height = source.naturalHeight
        const context = canvas.getContext("2d", { willReadFrequently: true })!
        context.drawImage(source, 0, 0)
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
        const qr = jsQR(pixels.data, pixels.width, pixels.height, { inversionAttempts: "dontInvert" })
        if (qr) {
          const corners = [qr.location.topLeftCorner, qr.location.topRightCorner, qr.location.bottomLeftCorner, qr.location.bottomRightCorner]
          const left = Math.max(0, Math.min(...corners.map(point => point.x)) - 10)
          const top = Math.max(0, Math.min(...corners.map(point => point.y)) - 10)
          const width = Math.min(canvas.width - left, Math.max(...corners.map(point => point.x)) - left + 10)
          const height = Math.min(canvas.height - top, Math.max(...corners.map(point => point.y)) - top + 10)
          area.current = { x: left / canvas.width, y: top / canvas.height, width: width / canvas.width, height: height / canvas.height }
          const cropped = document.createElement("canvas"); cropped.width = width; cropped.height = height
          cropped.getContext("2d")!.drawImage(canvas, left, top, width, height, 0, 0, width, height)
          const nextImage = cropped.toDataURL("image/png")
          if (nextImage !== previousImage) { previousImage = nextImage; firstQrAt.current = Date.now(); attempts.current = 0 }
          setImage(nextImage)
          lastQrAt.current = Date.now(); setMessage("请使用原设备上的抖音扫一扫，确认后会自动同步账号。")
        } else if (area.current && Date.now() - lastQrAt.current > 5000) {
          setImage(""); setMessage("二维码暂不可用，正在等待平台更新…")
          if (Date.now() - firstQrAt.current >= 5000 && attempts.current < 3) await refresh()
        }
      } catch (error) { console.warn("Identity QR read failed", error instanceof Error ? error.name : "UnknownError"); if (!cancelled.current) setMessage("二维码读取失败，请重新刷新。") }
      if (!cancelled.current) timer = setTimeout(poll, 1500)
    }
    void poll()
    return () => { cancelled.current = true; controller.abort(); clearTimeout(timer) }
    // The session is the lifetime boundary; refs hold refresh state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  return <div className="w-full space-y-3 rounded-xl border border-border p-3 text-center">
    <p className="text-sm font-semibold">验证方式</p>
    <button type="button" aria-pressed="true" disabled={busy} onClick={() => void refresh()} className="rounded border border-border px-3 py-2 text-sm">原设备扫码</button>
    {image && <img src={image} alt="抖音原设备扫码验证二维码" className="mx-auto h-56 w-56 bg-white object-contain" />}
    <p role="status" className="text-xs text-muted-foreground">{message}</p>
    <button type="button" disabled={busy} onClick={() => void refresh()} className="text-xs underline disabled:opacity-50">{busy ? "正在刷新…" : "刷新二维码"}</button>
    <p className="text-xs text-muted-foreground">二维码失效后自动尝试刷新，保持当前登录会话。</p>
  </div>
}
