"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"

import { API_ENDPOINTS } from "@/lib/env"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

const FALLBACK_WEBUI_URL = "http://127.0.0.1:9131"
const WEBUI_ASSET_REV = "hermes-composer-fix-20260519"
const STARTUP_ERROR_FALLBACK = "Hermes WebUI 启动失败，请检查 Hermes 运行时或模型配置。"

type HermesRuntime = {
  webui_running?: boolean
  webui_url?: string
  webui_port?: number
  dashboard_port?: number
}

type HermesBootState = "booting" | "ready" | "error"

function extractRuntime(payload: unknown): HermesRuntime | null {
  if (!payload || typeof payload !== "object") {
    return null
  }
  const data = (payload as { data?: { runtime?: HermesRuntime } }).data
  return data?.runtime ?? null
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

export default function AIAgentPage() {
  const [iframeKey, setIframeKey] = useState(0)
  const [backendBase, setBackendBase] = useState(API_ENDPOINTS.base)
  const [webuiUrl, setWebuiUrl] = useState(FALLBACK_WEBUI_URL)
  const [bootState, setBootState] = useState<HermesBootState>("booting")
  const [bootMessage, setBootMessage] = useState("正在启动 Hermes WebUI…")
  const [retryToken, setRetryToken] = useState(0)

  useEffect(() => {
    let active = true

    const applyRuntime = (runtime: HermesRuntime | null): boolean => {
      const runtimeUrl = String(runtime?.webui_url || "").trim()
      if (runtimeUrl) {
        setWebuiUrl(runtimeUrl)
      }
      if (runtime?.webui_running) {
        setBootState("ready")
        setBootMessage("")
        setIframeKey((current) => current + 1)
        return true
      }
      return false
    }

    const loadRuntimeStatus = async (baseUrl: string) => {
      const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, {
        cache: "no-store",
      })
      const payload = await response.json().catch(() => ({}))
      return extractRuntime(payload)
    }

    const boot = async () => {
      setBootState("booting")
      setBootMessage("正在启动 Hermes WebUI…")

      try {
        const baseUrl = await resolveRuntimeBackendBase()
        if (!active) {
          return
        }
        setBackendBase(baseUrl)

        const currentRuntime = await loadRuntimeStatus(baseUrl).catch(() => null)
        if (!active) {
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

        if (!active) {
          return
        }

        if (applyRuntime(runtime)) {
          return
        }

        for (let attempt = 0; attempt < 20; attempt += 1) {
          if (!active) {
            return
          }
          await new Promise((resolve) => setTimeout(resolve, 1000))
          const nextRuntime = await loadRuntimeStatus(baseUrl).catch(() => null)
          if (applyRuntime(nextRuntime)) {
            return
          }
        }

        throw new Error("Hermes WebUI 尚未就绪，请稍后重试。")
      } catch (error) {
        if (!active) {
          return
        }

        try {
          const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
          const runtime = await loadRuntimeStatus(baseUrl)
          if (applyRuntime(runtime)) {
            return
          }
        } catch {
          // Ignore status refresh failure and show the original startup error.
        }

        const message =
          error instanceof Error && error.message.trim() ? error.message.trim() : STARTUP_ERROR_FALLBACK
        setBootState("error")
        setBootMessage(message)
        setIframeKey(0)
      }
    }

    void boot()
    return () => {
      active = false
    }
  }, [retryToken])

  const iframeSrc = useMemo(
    () => `${webuiUrl}${webuiUrl.includes("?") ? "&" : "?"}syn_webui_rev=${WEBUI_ASSET_REV}`,
    [webuiUrl],
  )

  if (bootState !== "ready") {
    const isBooting = bootState === "booting"

    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-black px-6">
        <div className="w-full max-w-2xl rounded-[28px] border border-white/10 bg-white/5 p-8 text-white shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur">
          <p className="text-xs uppercase tracking-[0.28em] text-white/45">Hermes Agent</p>
          <h1 className="mt-4 text-3xl font-semibold">
            {isBooting ? "正在连接 Hermes WebUI" : "Hermes WebUI 未就绪"}
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-white/70">{bootMessage}</p>
          <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white/55">
            目标地址：{webuiUrl}
          </div>
          <div className="mt-2 text-xs text-white/35">Backend：{backendBase}</div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setRetryToken((current) => current + 1)}
              className="rounded-full border border-white/15 bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-white/90"
            >
              {isBooting ? "重新检查" : "重试启动"}
            </button>
            <Link
              href="/ai-agent/settings"
              className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-white/80 transition hover:border-white/30 hover:text-white"
            >
              打开 Hermes 设置
            </Link>
            <a
              href={webuiUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-white/60 transition hover:border-white/30 hover:text-white"
            >
              直接打开 WebUI
            </a>
          </div>
          {isBooting ? (
            <div className="mt-8 flex items-center gap-3 text-sm text-white/55">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />
              启动完成后会自动载入 Hermes WebUI。
            </div>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-4rem)] overflow-hidden bg-black">
      <iframe
        key={`${iframeSrc}:${iframeKey}`}
        src={iframeSrc}
        title="Hermes WebUI"
        className="block h-full w-full border-0 bg-black"
      />
    </div>
  )
}
