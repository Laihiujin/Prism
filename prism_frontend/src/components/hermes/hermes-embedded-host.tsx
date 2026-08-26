"use client"

import { useEffect, useMemo, useState } from "react"

import { API_ENDPOINTS } from "@/lib/env"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

const FALLBACK_WEBUI_URL = "http://127.0.0.1:9131"
const WEBUI_ASSET_REV = "hermes-composer-fix-20260519"
const STARTUP_ERROR_FALLBACK = "Hermes WebUI failed to start. Check the Hermes runtime and model configuration."

type HermesRuntime = {
  agent_installed?: boolean
  webui_installed?: boolean
  webui_running?: boolean
  webui_url?: string
  webui_port?: number
  dashboard_port?: number
}

function extractRuntime(payload: unknown): HermesRuntime | null {
  if (!payload || typeof payload !== "object") {
    return null
  }

  const data = (payload as { data?: HermesRuntime | { runtime?: HermesRuntime } }).data
  if (!data || typeof data !== "object") {
    return null
  }

  if ("runtime" in data && data.runtime && typeof data.runtime === "object") {
    return data.runtime
  }

  return data as HermesRuntime
}

function extractErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const responsePayload = payload as {
      message?: string
      detail?: string
      data?: { message?: string }
    }
    const candidate =
      responsePayload.data?.message || responsePayload.message || responsePayload.detail || ""
    if (String(candidate).trim()) {
      return String(candidate).trim()
    }
  }

  return `${STARTUP_ERROR_FALLBACK} (${status})`
}

export function HermesEmbeddedHost({ active }: { active: boolean }) {
  const [backendBase, setBackendBase] = useState(API_ENDPOINTS.base)
  const [webuiUrl, setWebuiUrl] = useState(FALLBACK_WEBUI_URL)
  const [retryToken, setRetryToken] = useState(0)
  const [ready, setReady] = useState(false)
  const [booting, setBooting] = useState(false)
  const [startupError, setStartupError] = useState("")

  useEffect(() => {
    let activeRequest = true

    const applyRuntime = (runtime: HermesRuntime | null): boolean => {
      const runtimeUrl = String(runtime?.webui_url || "").trim()
      if (runtimeUrl) {
        setWebuiUrl(runtimeUrl)
      }

      const running = Boolean(runtime?.webui_running)
      setReady(running)
      if (!running && runtime && (!runtime.agent_installed || !runtime.webui_installed)) {
        setStartupError("Hermes Agent 或 WebUI 尚未安装。请先完成本地 Hermes 运行时安装。")
      }
      return running
    }

    const loadRuntimeStatus = async (baseUrl: string) => {
      const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, {
        cache: "no-store",
      })
      const payload = await response.json().catch(() => ({}))
      return extractRuntime(payload)
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

        const currentRuntime = await loadRuntimeStatus(baseUrl).catch(() => null)
        if (!activeRequest) {
          return
        }
        if (applyRuntime(currentRuntime)) {
          return
        }

        const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/dashboard/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          cache: "no-store",
        })
        const payload = await response.json().catch(() => ({}))
        const runtime = extractRuntime(payload)

        if (!response.ok) {
          throw new Error(extractErrorMessage(payload, response.status))
        }

        if (!activeRequest) {
          return
        }

        if (applyRuntime(runtime)) {
          return
        }

        for (let attempt = 0; attempt < 20; attempt += 1) {
          if (!activeRequest) {
            return
          }
          await new Promise((resolve) => setTimeout(resolve, 1000))
          const nextRuntime = await loadRuntimeStatus(baseUrl).catch(() => null)
          if (applyRuntime(nextRuntime)) {
            return
          }
        }
        setStartupError(STARTUP_ERROR_FALLBACK)
      } catch (error) {
        setStartupError(error instanceof Error ? error.message : STARTUP_ERROR_FALLBACK)
        try {
          const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
          const runtime = await loadRuntimeStatus(baseUrl)
          applyRuntime(runtime)
        } catch {
          // The status panel below remains available even when the backend is offline.
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

  useEffect(() => {
    if (active) {
      setRetryToken((current) => current + 1)
    }
  }, [active])

  const iframeSrc = useMemo(
    () => `${webuiUrl}${webuiUrl.includes("?") ? "&" : "?"}prism_webui_rev=${WEBUI_ASSET_REV}`,
    [webuiUrl],
  )

  return (
    <div
      className={
        active
          ? "absolute inset-0 z-10 bg-card"
          : "pointer-events-none absolute inset-0 -z-10 bg-card opacity-0"
      }
      data-backend-base={backendBase}
    >
      {ready ? (
        <iframe
          src={iframeSrc}
          title="Hermes WebUI"
          className="block h-full w-full border-0 bg-card"
        />
      ) : (
        <div className="grid h-full place-items-center bg-card px-6 text-foreground">
          <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-foreground/5 p-8 text-center shadow-2xl">
            <div className="text-lg font-semibold">{booting ? "正在启动 Hermes Agent…" : "Hermes Agent 暂不可用"}</div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {startupError || "正在读取本地 Hermes 运行时状态。"}
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={() => setRetryToken((current) => current + 1)}
                disabled={booting}
                className="rounded-xl border border-border/70 px-4 py-2 text-sm disabled:opacity-50"
              >
                重试启动
              </button>
              <a href="/ai-agent/settings" className="rounded-xl bg-foreground px-4 py-2 text-sm text-background">
                打开运行时设置
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
