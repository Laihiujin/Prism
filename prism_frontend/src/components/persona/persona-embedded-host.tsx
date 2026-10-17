"use client"

import { useEffect, useMemo, useState } from "react"

import { API_ENDPOINTS } from "@/lib/env"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

const FALLBACK_DASHBOARD_URL = "http://127.0.0.1:5173"
const STARTUP_ERROR_FALLBACK = "Persona Dashboard 启动失败，请检查 Persona Studio 依赖与后端日志。"

type PersonaDashboardStatus = {
  running?: boolean
  pid?: number | null
  port?: number
  url?: string
  api_online?: boolean
  api_url?: string
  dir?: string
}

function extractStatus(payload: unknown): PersonaDashboardStatus | null {
  if (!payload || typeof payload !== "object") {
    return null
  }
  const result = (payload as { result?: PersonaDashboardStatus }).result
  if (!result || typeof result !== "object") {
    return null
  }
  return result as PersonaDashboardStatus
}

function extractErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const responsePayload = payload as {
      message?: string
      detail?: string
      result?: { message?: string }
    }
    const candidate =
      responsePayload.result?.message || responsePayload.message || responsePayload.detail || ""
    if (String(candidate).trim()) {
      return String(candidate).trim()
    }
  }
  return `${STARTUP_ERROR_FALLBACK} (HTTP ${status})`
}

export function PersonaEmbeddedHost({ active }: { active: boolean }) {
  const [backendBase, setBackendBase] = useState(API_ENDPOINTS.base)
  const [dashboardUrl, setDashboardUrl] = useState(FALLBACK_DASHBOARD_URL)
  const [retryToken, setRetryToken] = useState(0)
  const [ready, setReady] = useState(false)
  const [booting, setBooting] = useState(false)
  const [apiOnline, setApiOnline] = useState<boolean | undefined>(undefined)
  const [startupError, setStartupError] = useState("")

  useEffect(() => {
    let activeRequest = true

    const applyStatus = (status: PersonaDashboardStatus | null): boolean => {
      const statusUrl = String(status?.url || "").trim()
      if (statusUrl) {
        setDashboardUrl(statusUrl)
      }
      setApiOnline(status?.api_online)
      const running = Boolean(status?.running)
      setReady(running)
      return running
    }

    const loadStatus = async (baseUrl: string): Promise<PersonaDashboardStatus | null> => {
      const response = await fetch(`${baseUrl}/api/v1/persona/dashboard/status`, {
        cache: "no-store",
      })
      const payload = await response.json().catch(() => ({}))
      return extractStatus(payload)
    }

    const boot = async () => {
      if (!active) return
      setBooting(true)
      setStartupError("")
      try {
        const baseUrl = await resolveRuntimeBackendBase()
        if (!activeRequest) {
          return
        }
        setBackendBase(baseUrl)

        const currentStatus = await loadStatus(baseUrl).catch(() => null)
        if (!activeRequest) {
          return
        }
        if (applyStatus(currentStatus)) {
          return
        }

        const response = await fetch(`${baseUrl}/api/v1/persona/dashboard/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
        })
        const payload = await response.json().catch(() => ({}))
        const status = extractStatus(payload)

        if (!response.ok) {
          throw new Error(extractErrorMessage(payload, response.status))
        }

        if (!activeRequest) {
          return
        }

        if (applyStatus(status)) {
          return
        }

        // Vite dev server 冷启动需要时间（首次 npm install 后可能更久），轮询最多 45s
        for (let attempt = 0; attempt < 45; attempt += 1) {
          if (!activeRequest) {
            return
          }
          await new Promise((resolve) => setTimeout(resolve, 1000))
          const nextStatus = await loadStatus(baseUrl).catch(() => null)
          if (applyStatus(nextStatus)) {
            return
          }
        }
        setStartupError(STARTUP_ERROR_FALLBACK)
      } catch (error) {
        setStartupError(error instanceof Error ? error.message : STARTUP_ERROR_FALLBACK)
        try {
          const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
          const status = await loadStatus(baseUrl)
          applyStatus(status)
        } catch {
          // 状态面板保持可用
        }
      } finally {
        if (activeRequest) setBooting(false)
      }
    }

    void boot()
    return () => {
      activeRequest = false
    }
  }, [active, retryToken])

  const iframeSrc = useMemo(() => dashboardUrl, [dashboardUrl])

  return (
    <div
      className={
        active
          ? "absolute inset-0 z-10 bg-card"
          : "pointer-events-none absolute inset-0 -z-10 bg-card opacity-0"
      }
      data-backend-base={backendBase}
    >
      <details className="absolute left-4 right-4 top-3 z-20 rounded-lg border border-border bg-card p-3 text-sm shadow">
        <summary className="cursor-pointer font-medium">Persona 怎么用：每个账号保留一套独立浏览器环境</summary>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-muted-foreground">
          <li>先到代理管理添加线路、检测出口，并把账号绑定到固定代理；直连账号可跳过。</li>
          <li>到系统设置将浏览器后端选为 Persona，再到账号管理打开该账号的浏览器。Prism 自动关联环境。</li>
          <li>在该环境完成平台登录，后续继续使用同一账号、环境和代理。关闭窗口会保留登录状态。</li>
          <li>下方 Dashboard 用于查看环境和服务状态。已绑定 Persona 的账号需要 Persona 服务在线。</li>
        </ol>
        <div className="mt-3 flex gap-4"><a className="underline" href="/settings">浏览器设置</a><a className="underline" href="/account">账号管理</a><a className="underline" href="/ip-pool">代理管理</a></div>
      </details>
      {ready ? (
        <iframe
          src={iframeSrc}
          title="Persona Studio Dashboard"
          className="block h-full w-full border-0 bg-card pt-16"
        />
      ) : (
        <div className="grid h-full place-items-center bg-card px-6 text-foreground">
          <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-foreground/5 p-8 text-center shadow-2xl">
            <div className="text-lg font-semibold">
              {booting ? "正在启动 Persona Studio Dashboard…" : "Persona Dashboard 暂不可用"}
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {startupError || "正在读取 Persona Dashboard 运行时状态。"}
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-full border border-border/70 px-2.5 py-1">
                Persona API:{" "}
                {apiOnline === undefined
                  ? "检测中…"
                  : apiOnline
                    ? "在线"
                    : "离线"}
              </span>
              <span className="rounded-full border border-border/70 px-2.5 py-1">
                端口: {dashboardUrl.replace(/^https?:\/\//, "")}
              </span>
            </div>
            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={() => setRetryToken((current) => current + 1)}
                disabled={booting}
                className="rounded-xl border border-border/70 px-4 py-2 text-sm disabled:opacity-50"
              >
                重试启动
              </button>
              <a
                href="/persona-proxy"
                className="rounded-xl bg-foreground px-4 py-2 text-sm text-background"
              >
                打开代理网关
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
