"use client"

import { API_ENDPOINTS } from "@/lib/env"

function normalizeBackendBase(raw: string): string {
  const trimmed = String(raw || "").trim().replace(/\/+$/, "")
  return trimmed || API_ENDPOINTS.base
}

export async function resolveRuntimeBackendBase(): Promise<string> {
  if (typeof window === "undefined") {
    return API_ENDPOINTS.base
  }

  const electron = (window as typeof window & {
    electronAPI?: { app?: { getInfo?: () => Promise<{ backendUrl?: string }> } }
  }).electronAPI

  if (!electron?.app?.getInfo) {
    return API_ENDPOINTS.base
  }

  try {
    const info = await electron.app.getInfo()
    return normalizeBackendBase(info?.backendUrl || "")
  } catch {
    return API_ENDPOINTS.base
  }
}
