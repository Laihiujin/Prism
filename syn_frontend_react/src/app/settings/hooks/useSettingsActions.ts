"use client"

import { useEffect, useState } from "react"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"

interface LoadingState {
  refreshStatus: boolean
  restartAll: boolean
  restartBackend: boolean
  restartFrontend: boolean
  stopAll: boolean
  quitApp: boolean
  clearMaterials: boolean
  clearAccounts: boolean
  clearBrowser: boolean
  clearCache: boolean
  clearVideoData: boolean
  runSelfCheck: boolean
  forceKill: boolean
  exportLogs: boolean
  setBrowserHeadless: boolean
}

interface ServiceStatus {
  running: boolean
  pid?: number | null
  external?: boolean
}

interface RuntimeStatus {
  frontend?: ServiceStatus
  backend?: ServiceStatus
  supervisor?: ServiceStatus
  playwright_worker?: ServiceStatus
  celery_worker?: ServiceStatus
}

interface AppInfo {
  version?: string
  name?: string
  isPackaged?: boolean
  resourcesPath?: string
  playwrightBrowserPath?: string
  runtimeSettings?: RuntimeSettings
}

interface RuntimeSettings {
  browserHeadless: boolean
}

const isElectron = typeof window !== "undefined" && Boolean((window as any).electronAPI)

export function useSettingsActions() {
  const { toast } = useToast()
  const apiBase = API_ENDPOINTS.base || "http://localhost:7000"
  const [loading, setLoading] = useState<LoadingState>({
    refreshStatus: false,
    restartAll: false,
    restartBackend: false,
    restartFrontend: false,
    stopAll: false,
    quitApp: false,
    clearMaterials: false,
    clearAccounts: false,
    clearBrowser: false,
    clearCache: false,
    clearVideoData: false,
    runSelfCheck: false,
    forceKill: false,
    exportLogs: false,
    setBrowserHeadless: false,
  })
  const [status, setStatus] = useState<RuntimeStatus | null>(null)
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null)

  const setLoadingState = (key: keyof LoadingState, value: boolean) => {
    setLoading((prev) => ({ ...prev, [key]: value }))
  }

  const handleAction = async (
    key: keyof LoadingState,
    action: () => Promise<void>,
    successMessage: string
  ) => {
    setLoadingState(key, true)
    try {
      await action()
      toast({
        title: "Success",
        description: successMessage,
      })
    } catch (error: any) {
      toast({
        title: "Action failed",
        description: error.message || "Request failed",
        variant: "destructive",
      })
      throw error
    } finally {
      setLoadingState(key, false)
    }
  }

  const refreshStatus = async ({ silent = false }: { silent?: boolean } = {}) => {
    setLoadingState("refreshStatus", true)
    try {
      if (isElectron) {
        const electron = (window as any).electronAPI
        const nextStatus = electron.supervisor?.getStatus
          ? await electron.supervisor.getStatus()
          : await electron.system.getStatus()
        setStatus(nextStatus ?? null)
        if (electron.app?.getInfo) {
          setAppInfo(await electron.app.getInfo())
        }
      } else {
        setStatus(null)
        setAppInfo(null)
      }

      if (!silent) {
        toast({
          title: "Status refreshed",
          description: "Runtime status has been updated",
        })
      }
    } catch (error: any) {
      if (!silent) {
        toast({
          title: "Refresh failed",
          description: error.message || "Unable to load runtime status",
          variant: "destructive",
        })
      }
      throw error
    } finally {
      setLoadingState("refreshStatus", false)
    }
  }

  useEffect(() => {
    void refreshStatus({ silent: true })
  }, [])

  const restartAll = async () => {
    await handleAction("restartAll", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartAll()
        if (!result.success) {
          throw new Error(result.error || "Restart failed")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Restart failed")
        }
      }
      await refreshStatus({ silent: true })
    }, "All services restarted")
  }

  const restartBackend = async () => {
    await handleAction("restartBackend", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartBackend()
        if (!result.success) {
          throw new Error(result.error || "Backend restart failed")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart/backend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Backend restart failed")
        }
      }
      await refreshStatus({ silent: true })
    }, "Backend restarted")
  }

  const restartFrontend = async () => {
    await handleAction("restartFrontend", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartFrontend()
        if (!result.success) {
          throw new Error(result.error || "Frontend restart failed")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/restart-frontend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Frontend restart failed")
        }
      }
      await refreshStatus({ silent: true })
    }, "Frontend restarted")
  }

  const stopAll = async () => {
    await handleAction("stopAll", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.stopAll()
        if (!result.success) {
          throw new Error(result.error || "Stop failed")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Stop failed")
        }
      }
      await refreshStatus({ silent: true })
    }, "All services stopped")
  }

  const setBrowserHeadless = async (browserHeadless: boolean) => {
    await handleAction("setBrowserHeadless", async () => {
      if (!isElectron) {
        throw new Error("Desktop app only")
      }

      const electron = (window as any).electronAPI
      const result = await electron.settings.update({ browserHeadless })
      if (!result.success) {
        throw new Error(result.error || "Failed to update browser mode")
      }

      setAppInfo((prev) => ({
        ...(prev ?? {}),
        runtimeSettings: result.settings,
      }))

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "Services restart failed")
      }

      await refreshStatus({ silent: true })
    }, browserHeadless ? "Browser automation will run headless" : "Browser automation windows will be shown")
  }

  const quitApp = async () => {
    await handleAction("quitApp", async () => {
      if (!isElectron) {
        throw new Error("Desktop app only")
      }
      const result = await (window as any).electronAPI.system.quitApp()
      if (!result.success) {
        throw new Error(result.error || "Quit failed")
      }
    }, "Application is quitting")
  }

  const clearMaterials = async () => {
    await handleAction("clearMaterials", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-materials`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Clear materials failed")
      }
    }, "Materials cleared")
  }

  const clearAccounts = async () => {
    await handleAction("clearAccounts", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-accounts`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Clear accounts failed")
      }
    }, "Accounts and cookies cleared")
  }

  const clearBrowser = async () => {
    await handleAction("clearBrowser", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-browser`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Clear browser failed")
      }
    }, "Browser data cleared")
  }

  const clearCache = async () => {
    await handleAction("clearCache", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-cache`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Clear cache failed")
      }
    }, "Cache cleared")
  }

  const clearVideoData = async () => {
    await handleAction("clearVideoData", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-video-data`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Clear video data failed")
      }
    }, "Video data cleared")
  }

  const runSelfCheck = async () => {
    await handleAction("runSelfCheck", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/self-check`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Self-check failed")
      }
      const data = await response.json()
      if (data.status === "warning" && data.issues?.length) {
        throw new Error(`Issues found:\n${data.issues.join("\n")}`)
      }
    }, "Self-check completed")
  }

  const forceKillProcesses = async () => {
    await handleAction("forceKill", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.stopAll()
        if (!result.success) {
          throw new Error(result.error || "Force stop failed")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "Force stop failed")
        }
      }
      await refreshStatus({ silent: true })
    }, "Processes stopped")
  }

  const exportLogs = async () => {
    await handleAction("exportLogs", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/export-logs`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Export logs failed")
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `synapse-logs-${new Date().toISOString().split("T")[0]}.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    }, "Logs exported")
  }

  return {
    appInfo,
    status,
    loading,
    refreshStatus,
    restartAll,
    restartBackend,
    restartFrontend,
    stopAll,
    setBrowserHeadless,
    quitApp,
    clearMaterials,
    clearAccounts,
    clearBrowser,
    clearCache,
    clearVideoData,
    runSelfCheck,
    forceKillProcesses,
    exportLogs,
  }
}
