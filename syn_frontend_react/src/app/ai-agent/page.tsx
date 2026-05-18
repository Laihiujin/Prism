"use client"

import { useEffect, useState } from "react"

import { API_ENDPOINTS } from "@/lib/env"

const DASHBOARD_PORT = 9119
const WEBUI_PORT = 9131
const FALLBACK_WEBUI_URL = `http://127.0.0.1:${WEBUI_PORT}`
const WEBUI_ASSET_REV = "hermes-composer-fix-20260513c"

export default function AIAgentPage() {
  const [iframeKey, setIframeKey] = useState(0)
  const [webuiUrl, setWebuiUrl] = useState(FALLBACK_WEBUI_URL)

  useEffect(() => {
    let active = true

    const boot = async () => {
      try {
        const response = await fetch(`${API_ENDPOINTS.base}/api/v1/agent/config/hermes/dashboard/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ port: DASHBOARD_PORT, webui_port: WEBUI_PORT }),
        })
        const payload = await response.json().catch(() => ({}))
        const runtimeUrl = String(payload?.data?.runtime?.webui_url || "").trim()
        if (active && runtimeUrl) {
          setWebuiUrl(runtimeUrl)
        }
      } catch {
        // Best effort only. If WebUI is already running, the iframe still works.
      } finally {
        if (!active) return
        setTimeout(() => {
          if (active) {
            setIframeKey((current) => current + 1)
          }
        }, 1200)
      }
    }

    void boot()
    return () => {
      active = false
    }
  }, [])

  const iframeSrc = `${webuiUrl}${webuiUrl.includes("?") ? "&" : "?"}syn_webui_rev=${WEBUI_ASSET_REV}`

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
