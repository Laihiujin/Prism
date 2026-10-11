"use client"

import { useEffect, useState } from "react"
import { backendBaseUrl } from "@/lib/env"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type Runtime = {
  browsers?: Record<string, { installed?: boolean }>
  providerRegistry?: {
    active?: { provider: string; name: string; executablePath: string }
    providers?: { id: string; name: string; installed: boolean; userSelectable?: boolean; compatible?: boolean; category?: string }[]
  }
}

export function BrowserSelection() {
  const [runtime, setRuntime] = useState<Runtime>()
  const [choice, setChoice] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${backendBaseUrl}/api/v1/system/browser-runtime/status`, { signal: controller.signal, cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("无法读取已安装的浏览器")
        const data = await response.json()
        setRuntime(data.browserRuntimeInfo)
        setChoice(data.browserRuntimeInfo?.providerRegistry?.active?.provider || "")
      }).catch(problem => { if (!controller.signal.aborted) setError(problem.message) })
    return () => controller.abort()
  }, [])
  const options = [
    { id: "chromium", name: "项目 Chromium", installed: Boolean(runtime?.browsers?.chromium?.installed) },
    { id: "firefox", name: "Firefox", installed: Boolean(runtime?.browsers?.firefox?.installed) },
    ...(runtime?.providerRegistry?.providers || []).filter(provider => provider.userSelectable && provider.compatible && provider.category !== "persona"),
  ]
  const apply = async () => {
    setBusy(true); setError(""); setMessage("")
    try {
      const response = await fetch(`${backendBaseUrl}/api/v1/system/browser-runtime/apply/${encodeURIComponent(choice)}`, { method: "POST" })
      const data = await response.json()
      if (!response.ok || data.success === false) throw new Error(data.detail || data.error || "浏览器切换失败")
      setRuntime(data.browserRuntimeInfo)
      setMessage("已应用，新建登录和发布会话时生效。")
    } catch (problem) { setError(problem instanceof Error ? problem.message : "浏览器切换失败") }
    finally { setBusy(false) }
  }
  return <Card>
    <CardHeader><CardTitle>选择浏览器版本</CardTitle><CardDescription>选择实际启动的浏览器；下方平台偏好用于选择 Chromium 或 Firefox 引擎。</CardDescription></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-sm">当前选择：{runtime?.providerRegistry?.active?.name || "使用本地默认配置"}</p>
      {runtime?.providerRegistry?.active?.executablePath && <p className="break-all text-xs text-muted-foreground">{runtime.providerRegistry.active.executablePath}</p>}
      <div className="flex gap-2">
        <Select value={choice} onValueChange={setChoice} disabled={busy}>
          <SelectTrigger aria-label="浏览器版本"><SelectValue placeholder="选择已安装的浏览器" /></SelectTrigger>
          <SelectContent>{options.map(option => <SelectItem key={option.id} value={option.id} disabled={!option.installed}>{option.name}{!option.installed ? "（未安装）" : ""}</SelectItem>)}</SelectContent>
        </Select>
        <Button onClick={() => void apply()} disabled={busy || !options.some(option => option.id === choice && option.installed)}>{busy ? "应用中…" : "应用"}</Button>
      </div>
      <p className="text-xs text-muted-foreground">未安装的版本可在开发者工具中下载。已有会话继续使用原浏览器。</p>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {message && <p role="status" className="text-xs">{message}</p>}
    </CardContent>
  </Card>
}
