"use client"

import { useEffect, useMemo, useState } from "react"

import { API_ENDPOINTS } from "@/lib/env"
import { resolveRuntimeBackendBase } from "@/lib/runtime-backend"

const FALLBACK_WEBUI_URL = "http://127.0.0.1:9131"
const WEBUI_ASSET_REV = "hermes-composer-fix-20260519"
const STARTUP_ERROR_FALLBACK = "Hermes WebUI failed to start. Check the Hermes runtime and model configuration."

type HermesRuntime = {
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

  useEffect(() => {
    let activeRequest = true

    const applyRuntime = (runtime: HermesRuntime | null): boolean => {
      const runtimeUrl = String(runtime?.webui_url || "").trim()
      if (runtimeUrl) {
        setWebuiUrl(runtimeUrl)
      }

      return Boolean(runtime?.webui_running)
    }

    const loadRuntimeStatus = async (baseUrl: string) => {
      const response = await fetch(`${baseUrl}/api/v1/agent/config/hermes/runtime`, {
        cache: "no-store",
      })
      const payload = await response.json().catch(() => ({}))
      return extractRuntime(payload)
    }

    const boot = async () => {
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
      } catch {
        try {
          const baseUrl = await resolveRuntimeBackendBase().catch(() => API_ENDPOINTS.base)
          const runtime = await loadRuntimeStatus(baseUrl)
          applyRuntime(runtime)
        } catch {
          // Keep the current iframe target as-is and let the embedded page recover itself.
        }
      }
    }

    void boot()
    return () => {
      activeRequest = false
    }
  }, [retryToken])

  useEffect(() => {
    if (active) {
      setRetryToken((current) => current + 1)
    }
  }, [active])

  const iframeSrc = useMemo(
    () => `${webuiUrl}${webuiUrl.includes("?") ? "&" : "?"}syn_webui_rev=${WEBUI_ASSET_REV}`,
    [webuiUrl],
  )

  return (
    <div
      className={
        active
          ? "absolute inset-0 z-10 bg-black"
          : "pointer-events-none absolute inset-0 -z-10 bg-black opacity-0"
      }
      data-backend-base={backendBase}
    >
      <iframe
        src={iframeSrc}
        title="Hermes WebUI"
        className="block h-full w-full border-0 bg-black"
      />
    </div>
  )
}
