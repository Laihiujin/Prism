"use client"

import { startTransition, useCallback, useEffect, useMemo, useState } from "react"
import { ExternalLink, RefreshCw, Settings2, Terminal, Wrench } from "lucide-react"

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

export default function HermesSettingsPage() {
  const [runtime, setRuntime] = useState<HermesRuntime | null>(null)
  const [backendBase, setBackendBase] = useState(API_ENDPOINTS.base)

  const loadRuntime = useCallback(async () => {
    const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
    setBackendBase(baseUrl)
    try {
      const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, { cache: "no-store" })
      const payload = await response.json()
      setRuntime(payload?.data || null)
    } catch {
      setRuntime(null)
    }
  }, [])

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
              className="rounded-xl border border-white/10 text-white/80 hover:text-white"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
          </div>
        }
      />

      <div className="mx-auto max-w-5xl space-y-6">
        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-primary" />
              入口
            </CardTitle>
            <CardDescription className="text-white/60">
              Backend 以 Electron 运行时注入为准，不再依赖编译期的 7000 默认值。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-white/80">
            <div>Runtime Backend：{backendBase}</div>
            <div>Dashboard：{dashboardUrl}</div>
            <div>WebUI：{webuiUrl}</div>
            <div className="flex flex-wrap gap-3 pt-2">
              <Button asChild variant="outline" className="border-white/10 bg-white/5">
                <a href="/settings">
                  <Settings2 className="mr-2 h-4 w-4" />
                  打开系统设置
                </a>
              </Button>
              <Button asChild variant="outline" className="border-white/10 bg-white/5">
                <a href={dashboardUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  打开 Dashboard
                </a>
              </Button>
              <Button asChild variant="outline" className="border-white/10 bg-white/5">
                <a href={webuiUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  打开 WebUI
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wrench className="h-5 w-5 text-primary" />
              本地运行时
            </CardTitle>
            <CardDescription className="text-white/60">
              用于确认 Hermes CLI、Dashboard 和 WebUI 是否真的安装并跑在当前 Electron 使用的环境里。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-white/80">
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
            <div className="rounded-xl border border-white/10 bg-black/40 p-3 text-xs text-white/70">
              CLI 命令
              <div className="mt-2 break-all font-mono text-white">{cliCommand}</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
