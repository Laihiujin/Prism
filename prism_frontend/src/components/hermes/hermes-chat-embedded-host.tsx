"use client"

import { useEffect, useState } from "react"

import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

// Prism's desktop runtime serves the Hermes WebUI on 9131 by default; the
// source/PM2 stack serves it on 8788. The authoritative value is reported by
// the backend /api/v1/agent/config/hermes/runtime endpoint (webui_url), which
// we resolve below. This fallback only applies while the backend is
// unreachable, so it keeps the embedded chat usable in the common desktop case.
const FALLBACK_WEBUI_URL = "http://127.0.0.1:9131"
const STARTUP_ERROR_FALLBACK = "Hermes WebUI failed to start. Check the Hermes runtime and model configuration."

type HermesRuntime = {
  agent_installed?: boolean
  webui_installed?: boolean
  webui_running?: boolean
  webui_url?: string
  webui_port?: number
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
    return data.runtime as HermesRuntime
  }

  return data as HermesRuntime
}

export function HermesChatEmbeddedHost({ active }: { active: boolean }) {
  const [webuiUrl, setWebuiUrl] = useState(FALLBACK_WEBUI_URL)
  const [ready, setReady] = useState(false)
  const [startupError, setStartupError] = useState("")
  const [retryToken, setRetryToken] = useState(0)

  useEffect(() => {
    let activeRequest = true

    const boot = async () => {
      if (!active) return
      setStartupError("")
      try {
        const baseUrl = await resolveRuntimeBackendBase()
        if (!activeRequest) {
          return
        }

        const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, {
          cache: "no-store",
        })
        const payload = await response.json().catch(() => ({}))
        const runtime = extractRuntime(payload)
        if (!activeRequest) {
          return
        }

        const runtimeUrl = String(runtime?.webui_url || "").trim()
        if (runtimeUrl) {
          setWebuiUrl(runtimeUrl)
        }

        const running = Boolean(runtime?.webui_running) || Boolean(runtimeUrl)
        setReady(running)

        if (!running && runtime && !runtime.webui_installed) {
          setStartupError("Hermes WebUI 尚未安装。请先完成本地 Hermes 运行时安装。")
        } else if (!running) {
          setStartupError(STARTUP_ERROR_FALLBACK)
        }
      } catch {
        if (!activeRequest) {
          return
        }
        // Backend unreachable — keep the fallback URL so the chat iframe still
        // loads when the desktop supervisor is already serving the WebUI.
        setReady(true)
        setStartupError("")
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

  return (
    <div
      className={
        active
          ? "absolute inset-0 z-10 bg-black"
          : "pointer-events-none absolute inset-0 -z-10 bg-black opacity-0"
      }
    >
      {ready ? (
        <iframe
          src={webuiUrl}
          title="HermesChat"
          className="block h-full w-full border-0 bg-black"
        />
      ) : (
        <div className="grid h-full place-items-center bg-black px-6 text-foreground">
          <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-foreground/5 p-8 text-center shadow-2xl">
            <div className="text-lg font-semibold">Hermes Chat 暂不可用</div>
            <p className="mt-3 text-sm leading-6 text-foreground/70">
              {startupError || "正在读取本地 Hermes 运行时状态。"}
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={() => setRetryToken((current) => current + 1)}
                className="rounded-xl border border-border/70 px-4 py-2 text-sm"
              >
                重试
              </button>
              <a
                href="/ai-agent/settings"
                className="rounded-xl bg-foreground px-4 py-2 text-sm text-background"
              >
                打开运行时设置
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
