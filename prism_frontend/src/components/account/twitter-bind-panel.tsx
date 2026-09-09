"use client"

/**
 * 推特登录/绑定面板（账号页弹窗内嵌）。
 *
 * 与其它平台不同：推特没有网页 cookie，登录走 xurl CLI 的 OAuth 2.0 PKCE（视觉流程）。
 * 账号需先在「运行后端的机器」上注册 app（一次性，含密钥，手动）：
 *     xurl auth apps add my-app --client-id ... --client-secret ...
 * 之后即可：
 *   1) 一键登录：POST /api/v1/accounts/twitter/login {app} → 在后端机器弹出浏览器，用户授权。
 *   2) 轮询：POST /api/v1/accounts/twitter/whoami {app} 直到 token 就绪（返回 @handle）。
 *   3) 绑定：POST /api/v1/accounts/twitter/bind {app} → 写入账号库（cookie_file = xurl app 名）。
 *
 * 本组件/接口一律不接收、不传递任何密钥（client-id/secret/token）。
 */

import { useEffect, useRef, useState } from "react"
import { Globe, Loader2, ShieldCheck, TerminalSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/components/ui/use-toast"
import { backendBaseUrl } from "@/lib/env"

interface Props {
  onLoginDone?: () => void
}

export function TwitterBindPanel({ onLoginDone }: Props) {
  const { toast } = useToast()
  const [app, setApp] = useState("")
  const [busy, setBusy] = useState<"check" | "bind" | "login" | null>(null)
  const [handle, setHandle] = useState<string | null>(null)
  const [waitingAuth, setWaitingAuth] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const jsonPost = (path: string, body: Record<string, string>) =>
    fetch(`${backendBaseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    setWaitingAuth(false)
  }

  const check = async () => {
    const appName = app.trim()
    if (!appName) {
      toast({ variant: "destructive", title: "请输入 xurl app 名" })
      return
    }
    setBusy("check")
    setHandle(null)
    try {
      const res = await jsonPost("/api/v1/accounts/twitter/whoami", { app: appName })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data?.success || !data?.data?.ok) {
        throw new Error(data?.detail || data?.data?.reason || `检测失败（HTTP ${res.status}）`)
      }
      setHandle(data.data.handle)
      toast({ variant: "success", title: "账号已检测", description: `@${data.data.handle}` })
    } catch (err) {
      toast({ variant: "destructive", title: "检测失败", description: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(null)
    }
  }

  const login = async () => {
    const appName = app.trim()
    if (!appName) {
      toast({ variant: "destructive", title: "请输入 xurl app 名" })
      return
    }
    setBusy("login")
    setHandle(null)
    try {
      const res = await jsonPost("/api/v1/accounts/twitter/login", { app: appName })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data?.success) {
        throw new Error(data?.detail || `启动登录失败（HTTP ${res.status}）`)
      }
      toast({ title: "已启动浏览器授权", description: "请在运行后端机器的浏览器中完成授权" })
      setWaitingAuth(true)
      setBusy(null)
      // 轮询 whoami，直到 token 就绪返回 handle
      const startedAt = Date.now()
      pollRef.current = setInterval(async () => {
        if (Date.now() - startedAt > 5 * 60 * 1000) {
          stopPolling()
          setBusy(null)
          toast({ title: "授权超时", description: "请在浏览器完成授权后，点「检测」确认后再绑定" })
          return
        }
        try {
          const wRes = await jsonPost("/api/v1/accounts/twitter/whoami", { app: appName })
          const wData = await wRes.json().catch(() => ({}))
          if (wRes.ok && wData?.success && wData?.data?.ok && wData?.data?.handle) {
            stopPolling()
            setHandle(wData.data.handle)
            setBusy(null)
            toast({ variant: "success", title: "授权成功", description: `@${wData.data.handle} 已就绪，可绑定` })
          }
        } catch {
          // 尚未就绪，继续轮询
        }
      }, 2500)
    } catch (err) {
      toast({ variant: "destructive", title: "启动登录失败", description: err instanceof Error ? err.message : String(err) })
      setBusy(null)
    }
  }

  const bind = async () => {
    const appName = app.trim()
    if (!appName) {
      toast({ variant: "destructive", title: "请输入 xurl app 名" })
      return
    }
    setBusy("bind")
    try {
      const res = await jsonPost("/api/v1/accounts/twitter/bind", { app: appName })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data?.success) {
        throw new Error(data?.detail || `绑定失败（HTTP ${res.status}）`)
      }
      toast({ variant: "success", title: "推特绑定成功", description: `@${data.data?.handle || appName} 已加入矩阵` })
      onLoginDone?.()
    } catch (err) {
      toast({ variant: "destructive", title: "绑定失败", description: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/70 bg-card p-4">
      <div className="flex items-center gap-2">
        <Globe className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-semibold">推特（X）账号绑定</p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-black px-3 py-2 text-[11px] leading-4 text-muted-foreground">
        <TerminalSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-foreground/40" />
        <p>
          首次使用需在<b className="text-foreground/70">运行后端的机器</b>上注册一个 app（一次性，含密钥，需手动）：
          <code className="mx-1 rounded bg-white/10 px-1 font-mono text-[10px] text-foreground/80">
            xurl auth apps add my-app --client-id ... --client-secret ...
          </code>
          之后可直接点下方「登录」，浏览器会弹出授权。
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground">xurl app 名（@handle）</Label>
        <div className="flex items-center gap-2">
          <Input
            placeholder="my-app"
            value={app}
            onChange={(event) => {
              setApp(event.target.value)
              setHandle(null)
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") void bind()
            }}
            className="rounded-xl border-border/70 bg-card text-foreground placeholder:text-foreground/40"
          />
          <Button type="button" variant="secondary" size="sm" className="shrink-0 rounded-xl" disabled={!!busy || waitingAuth} onClick={check}>
            {busy === "check" ? <Loader2 className="h-4 w-4 animate-spin" /> : "检测"}
          </Button>
        </div>
        <p className="text-[10px] text-foreground/40">填注册 app 时用的名字（或 app@handle）</p>
      </div>

      {waitingAuth && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200/90">
          <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
          <span>已在运行后端机器的浏览器打开授权页，请完成授权；就绪后自动确认…</span>
        </div>
      )}

      {handle && (
        <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-background p-2 text-xs text-foreground/80">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span className="font-mono text-[13px]">@{handle}</span>
          <span className="text-muted-foreground">已通过 xurl 认证</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <Button type="button" variant="outline" className="rounded-xl" disabled={!!busy || waitingAuth || !app.trim()} onClick={login}>
          {busy === "login" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
          登录 X 账号（浏览器）
        </Button>
        <Button type="button" className="rounded-xl" disabled={!!busy || !app.trim()} onClick={bind}>
          {busy === "bind" ? <Loader2 className="h-4 w-4 animate-spin" /> : "绑定账号"}
        </Button>
      </div>
    </div>
  )
}
