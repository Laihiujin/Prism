"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Monitor, X, RefreshCw } from "lucide-react"
import { BrowserViewport } from "@/components/account/remote-login-view"

type LoginSession = { id: string; platform?: string; kind?: string }
const platformNames: Record<string, string> = {
  douyin: "抖音", kuaishou: "快手", xiaohongshu: "小红书", bilibili: "B站", tencent: "视频号",
  "1": "小红书", "2": "视频号", "3": "抖音", "4": "快手", "5": "B站",
}

export function BrowserPanel() {
  const [open, setOpen] = useState(false)
  const [session, setSession] = useState<LoginSession | null>(null)
  const [generation, setGeneration] = useState(0)

  useEffect(() => {
    const sync = () => {
      let next: LoginSession | null = null
      try {
        const raw = sessionStorage.getItem("prism-active-browser") || sessionStorage.getItem("prism-active-login")
        const parsed = raw ? JSON.parse(raw) : null
        if (typeof parsed?.id === "string" && parsed.id) next = parsed
      } catch { /* An unavailable or invalid session is shown as an empty panel. */ }
      setSession(current => current?.id === next?.id && current?.platform === next?.platform ? current : next)
    }
    sync()
    const show = () => { sync(); setOpen(true) }
    window.addEventListener("prism-browser-open", show)
    const timer = setInterval(sync, 1000)
    window.addEventListener("storage", sync)
    return () => { clearInterval(timer); window.removeEventListener("storage", sync); window.removeEventListener("prism-browser-open", show) }
  }, [])

  return <>
    {!open && <button type="button" onClick={() => setOpen(true)} aria-label="打开浏览器面板" style={{ pointerEvents: "auto" }}
      className="fixed right-0 top-1/2 z-[70] flex items-center gap-2 rounded-l-lg border border-r-0 border-border bg-background px-3 py-3 text-sm shadow-lg hover:bg-accent">
      <Monitor className="h-4 w-4" />浏览器
      {session && <span className="h-2 w-2 rounded-full bg-green-500" aria-label="有登录会话" />}
    </button>}
    {open && <aside aria-label="远程浏览器面板" style={{ pointerEvents: "auto" }} className="fixed inset-y-0 right-0 z-[80] flex w-full max-w-[760px] flex-col border-l border-border bg-background shadow-2xl">
      <div className="flex items-center justify-between border-b border-border p-4">
        <div className="flex items-center gap-2"><Monitor className="h-4 w-4" /><h2 className="text-sm font-semibold">浏览器</h2></div>
        <div className="flex gap-2">
          {session && <button type="button" onClick={() => setGeneration(value => value + 1)} aria-label="重新连接浏览器" className="rounded p-2 hover:bg-accent"><RefreshCw className="h-4 w-4" /></button>}
          <button type="button" onClick={() => setOpen(false)} aria-label="关闭浏览器面板" className="rounded p-2 hover:bg-accent"><X className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {session ? <>
          <div className="flex items-center gap-2 text-sm"><span className="h-2 w-2 rounded-full bg-green-500" />{platformNames[session.platform || ""] || "平台"} · {session.kind === "creator" ? "创作者中心" : "登录会话"}</div>
          <BrowserViewport key={`${session.id}:${generation}`} sessionId={session.id} />
          <p className="text-xs text-muted-foreground">关闭面板后浏览器仍会保留。可直接点击、拖动操作画面。</p>
        </> : <div className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
          <Monitor className="h-9 w-9 text-muted-foreground" />
          <p className="text-sm font-medium">暂无已连接的浏览器</p>
          <p className="text-xs text-muted-foreground">在账号管理打开创作者中心，或开始扫码、短信登录后，画面会显示在这里。</p>
          <Link href="/account" onClick={() => setOpen(false)} className="rounded border border-border px-4 py-2 text-sm hover:bg-accent">前往账号管理</Link>
        </div>}
      </div>
    </aside>}
  </>
}
