"use client"

import { startTransition, useCallback, useEffect, useMemo, useState } from "react"
import { Download, ExternalLink, RefreshCw, Settings2, Terminal, Wrench } from "lucide-react"

import { PageHeader } from "@/components/layout/page-scaffold"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { API_ENDPOINTS } from "@/lib/env"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

type HermesRuntime = {
  source_path?: string
  webui_path?: string
  dashboard_dist_path?: string
  home_path?: string
  webui_state_path?: string
  workspace_root?: string
  python_path?: string
  wrapper_path?: string | null
  git_bash_path?: string | null
  agent_installed?: boolean
  official_dashboard_installed?: boolean
  webui_installed?: boolean
  gui_installed?: boolean
  preferred_dashboard_backend?: "official" | "webui" | null
  gateway_pid?: number | null
  gateway_running?: boolean
  gateway_state?: string
  dashboard_backend?: "official" | "webui" | null
  dashboard_url?: string
  dashboard_running?: boolean
  webui_url?: string
  webui_running?: boolean
}

type HermesUpdateStatus = {
  settings: { enabled: boolean; interval_hours: number; branch: string }
  installed?: boolean
  local_revision?: string | null
  remote_revision?: string | null
  update_available?: boolean
  updating?: boolean
  last_checked_at?: string | null
  last_updated_at?: string | null
  last_error?: string | null
  preserved_home_path?: string
}

export default function HermesSettingsPage() {
  const [runtime, setRuntime] = useState<HermesRuntime | null>(null)
  const [backendBase, setBackendBase] = useState(API_ENDPOINTS.base)
  const [updateStatus, setUpdateStatus] = useState<HermesUpdateStatus | null>(null)
  const [updateBusy, setUpdateBusy] = useState(false)

  const loadRuntime = useCallback(async () => {
    const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
    setBackendBase(baseUrl)
    try {
      const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, { cache: "no-store" })
      const payload = await response.json()
      setRuntime(payload?.data || null)
      const updateResponse = await fetch(`${baseUrl}/api/v1/agent/config/hermes/update`, { cache: "no-store" })
      const updatePayload = await updateResponse.json()
      setUpdateStatus(updatePayload?.data || null)
    } catch {
      setRuntime(null)
    }
  }, [])

  const updateAction = useCallback(async (action: "check" | "apply") => {
    setUpdateBusy(true)
    try {
      const response = await fetch(`${backendBase}/api/v1/agent/config/hermes/update/${action}`, { method: "POST" })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.detail || "Hermes 更新操作失败")
      setUpdateStatus(payload?.data || null)
      if (action === "apply") await loadRuntime()
    } finally {
      setUpdateBusy(false)
    }
  }, [backendBase, loadRuntime])

  const saveUpdateSettings = useCallback(async (next: HermesUpdateStatus["settings"]) => {
    setUpdateBusy(true)
    try {
      const response = await fetch(`${backendBase}/api/v1/agent/config/hermes/update/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload?.detail || "保存更新策略失败")
      setUpdateStatus(payload?.data || null)
    } finally {
      setUpdateBusy(false)
    }
  }, [backendBase])

  useEffect(() => {
    let active = true

    const run = async () => {
      const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
      if (!active) return
      setBackendBase(baseUrl)
      try {
        const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, { cache: "no-store" })
        const payload = await response.json()
        if (!active) return
        startTransition(() => {
          setRuntime(payload?.data || null)
        })
        const updateResponse = await fetch(`${baseUrl}/api/v1/agent/config/hermes/update`, { cache: "no-store" })
        const updatePayload = await updateResponse.json()
        if (active) setUpdateStatus(updatePayload?.data || null)
      } catch {
        if (!active) return
        startTransition(() => {
          setRuntime(null)
        })
      }
    }

    void run()
    return () => {
      active = false
    }
  }, [])

  const dashboardUrl = runtime?.dashboard_url || "http://127.0.0.1:9119"
  const webuiUrl = runtime?.webui_url || "http://127.0.0.1:9131"

  const cliCommand = useMemo(() => {
    if (runtime?.wrapper_path) {
      return `powershell -ExecutionPolicy Bypass -File "${runtime.wrapper_path}"`
    }
    if (runtime?.python_path) {
      return `"${runtime.python_path}" -m hermes_cli.main`
    }
    return `powershell -ExecutionPolicy Bypass -File "scripts\\hermes\\hermes.ps1"`
  }, [runtime?.python_path, runtime?.wrapper_path])

  return (
    <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/ai-agent">Hermes Agent</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>运行时与入口</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <PageHeader
        title="Hermes Agent 设置"
        description="这里显示 Electron 当前正在使用的 Hermes 运行时、Dashboard 和 WebUI 入口。"
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void loadRuntime()}
              className="rounded-xl border border-border/70 text-foreground/80 hover:text-foreground"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
          </div>
        }
      />

      <div className="mx-auto max-w-5xl space-y-6">
        <Card className="border-border/70 bg-black">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5 text-primary" />
              上游更新
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              定时同步 NousResearch/hermes-agent。更新只替换程序代码，Hermes Home 中的模型、Gateway、MCP 与 WebUI 状态会保留。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-foreground/80">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={updateStatus?.settings.enabled ?? true}
                  disabled={updateBusy || !updateStatus}
                  onChange={(event) => updateStatus && void saveUpdateSettings({ ...updateStatus.settings, enabled: event.target.checked })}
                />
                自动更新
              </label>
              <label className="flex items-center gap-2">
                检查间隔
                <select
                  className="rounded-lg border border-border/70 bg-card/40 px-3 py-2"
                  value={updateStatus?.settings.interval_hours ?? 24}
                  disabled={updateBusy || !updateStatus}
                  onChange={(event) => updateStatus && void saveUpdateSettings({ ...updateStatus.settings, interval_hours: Number(event.target.value) })}
                >
                  <option value={6}>每 6 小时</option>
                  <option value={12}>每 12 小时</option>
                  <option value={24}>每天</option>
                  <option value={72}>每 3 天</option>
                  <option value={168}>每周</option>
                </select>
              </label>
              <div>分支：{updateStatus?.settings.branch || "main"}</div>
            </div>
            <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
              <div>当前版本：{updateStatus?.local_revision?.slice(0, 10) || "未检测"}</div>
              <div>上游版本：{updateStatus?.remote_revision?.slice(0, 10) || "尚未检查"}</div>
              <div>上次检查：{updateStatus?.last_checked_at ? new Date(updateStatus.last_checked_at).toLocaleString() : "从未"}</div>
              <div>上次更新：{updateStatus?.last_updated_at ? new Date(updateStatus.last_updated_at).toLocaleString() : "从未"}</div>
              <div className="md:col-span-2">保留配置目录：{updateStatus?.preserved_home_path || runtime?.home_path || "未检测"}</div>
            </div>
            {updateStatus?.last_error && <div className="rounded-lg border border-white/30 bg-black p-3 text-white">{updateStatus.last_error}</div>}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" disabled={updateBusy} onClick={() => void updateAction("check")}>
                <RefreshCw className={`mr-2 h-4 w-4 ${updateBusy ? "animate-spin" : ""}`} />检查更新
              </Button>
              <Button disabled={updateBusy || !updateStatus?.update_available} onClick={() => void updateAction("apply")}>
                <Download className="mr-2 h-4 w-4" />{updateStatus?.updating ? "更新中" : "立即更新"}
              </Button>
              <span>
                {!updateStatus?.installed
                  ? "尚未安装 Hermes Agent"
                  : updateStatus.update_available
                    ? "发现新版本"
                    : "当前已是最新版本"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-black">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-primary" />
              入口
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Backend 以 Electron 运行时注入为准，不再依赖编译期的 7000 默认值。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-foreground/80">
            <div>Runtime Backend：{backendBase}</div>
            <div>Dashboard：{dashboardUrl}</div>
            <div>WebUI：{webuiUrl}</div>
            <div className="flex flex-wrap gap-3 pt-2">
              <Button asChild variant="outline" className="border-border/70 bg-black">
                <a href="/settings">
                  <Settings2 className="mr-2 h-4 w-4" />
                  打开系统设置
                </a>
              </Button>
              <Button asChild variant="outline" className="border-border/70 bg-black">
                <a href={dashboardUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  打开 Dashboard
                </a>
              </Button>
              <Button asChild variant="outline" className="border-border/70 bg-black">
                <a href={webuiUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  打开 WebUI
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-black">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wrench className="h-5 w-5 text-primary" />
              本地运行时
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              用于确认 Hermes CLI、Dashboard 和 WebUI 是否真的安装并跑在当前 Electron 使用的环境里。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-foreground/80">
            <div>Agent 运行时：{runtime?.agent_installed ? "已安装" : "未安装"}</div>
            <div>官方 Dashboard：{runtime?.official_dashboard_installed ? "已安装" : "未安装"}</div>
            <div>兼容 WebUI：{runtime?.webui_installed ? "已安装" : "未安装"}</div>
            <div>共享 Gateway：{runtime?.gateway_running ? `运行中，PID ${runtime?.gateway_pid ?? "-"}` : `未运行，${runtime?.gateway_state || "stopped"}`}</div>
            <div>Dashboard 状态：{runtime?.dashboard_running ? `运行中，${dashboardUrl}` : `未运行，${dashboardUrl}`}</div>
            <div>WebUI 状态：{runtime?.webui_running ? `运行中，${webuiUrl}` : `未运行，${webuiUrl}`}</div>
            <div>源码目录：{runtime?.source_path || "未检测到"}</div>
            <div>Dashboard dist：{runtime?.dashboard_dist_path || "未检测到"}</div>
            <div>WebUI 目录：{runtime?.webui_path || "未检测到"}</div>
            <div>Hermes Home：{runtime?.home_path || "未检测到"}</div>
            <div>工作区目录：{runtime?.workspace_root || "未检测到"}</div>
            <div>Python 路径：{runtime?.python_path || "未检测到"}</div>
            <div>Git Bash：{runtime?.git_bash_path || "未检测到"}</div>
            <div className="rounded-xl border border-border/70 bg-card/40 p-3 text-xs text-foreground/70">
              CLI 命令
              <div className="mt-2 break-all font-mono text-foreground">{cliCommand}</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
