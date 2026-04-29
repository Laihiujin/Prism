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
        title: "操作成功",
        description: successMessage,
      })
    } catch (error: any) {
      toast({
        title: "操作失败",
        description: error.message || "请求失败",
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
          title: "状态已刷新",
          description: "运行时状态已更新",
        })
      }
    } catch (error: any) {
      if (!silent) {
        toast({
          title: "刷新失败",
          description: error.message || "无法加载运行时状态",
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
          throw new Error(result.error || "重启失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "重启失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "所有服务已重启")
  }

  const restartBackend = async () => {
    await handleAction("restartBackend", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartBackend()
        if (!result.success) {
          throw new Error(result.error || "后端重启失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart/backend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "后端重启失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "后端已重启")
  }

  const restartFrontend = async () => {
    await handleAction("restartFrontend", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartFrontend()
        if (!result.success) {
          throw new Error(result.error || "前端重启失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/restart-frontend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "前端重启失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "前端已重启")
  }

  const stopAll = async () => {
    await handleAction("stopAll", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.stopAll()
        if (!result.success) {
          throw new Error(result.error || "停止失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "停止失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "所有服务已停止")
  }

  const setBrowserHeadless = async (browserHeadless: boolean) => {
    await handleAction("setBrowserHeadless", async () => {
      if (!isElectron) {
        throw new Error("仅桌面版可用")
      }

      const electron = (window as any).electronAPI
      const result = await electron.settings.update({ browserHeadless })
      if (!result.success) {
        throw new Error(result.error || "浏览器模式更新失败")
      }

      setAppInfo((prev) => ({
        ...(prev ?? {}),
        runtimeSettings: result.settings,
      }))

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "服务重启失败")
      }

      await refreshStatus({ silent: true })
    }, browserHeadless ? "自动化浏览器将以无头模式运行" : "自动化浏览器窗口将显示出来")
  }

  const quitApp = async () => {
    await handleAction("quitApp", async () => {
      if (!isElectron) {
        throw new Error("仅桌面版可用")
      }
      const result = await (window as any).electronAPI.system.quitApp()
      if (!result.success) {
        throw new Error(result.error || "退出失败")
      }
    }, "应用正在退出")
  }

  const clearMaterials = async () => {
    await handleAction("clearMaterials", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-materials`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理素材失败")
      }
    }, "素材已清理")
  }

  const clearAccounts = async () => {
    await handleAction("clearAccounts", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-accounts`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理账号失败")
      }
    }, "账号和 Cookie 已清理")
  }

  const clearBrowser = async () => {
    await handleAction("clearBrowser", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-browser`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理浏览器失败")
      }
    }, "浏览器数据已清理")
  }

  const clearCache = async () => {
    await handleAction("clearCache", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-cache`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理缓存失败")
      }
    }, "缓存已清理")
  }

  const clearVideoData = async () => {
    await handleAction("clearVideoData", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-video-data`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理视频数据失败")
      }
    }, "视频数据已清理")
  }

  const runSelfCheck = async () => {
    await handleAction("runSelfCheck", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/self-check`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "自检失败")
      }
      const data = await response.json()
      if (data.status === "warning" && data.issues?.length) {
        throw new Error(`发现问题：\n${data.issues.join("\n")}`)
      }
    }, "自检已完成")
  }

  const forceKillProcesses = async () => {
    await handleAction("forceKill", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.stopAll()
        if (!result.success) {
          throw new Error(result.error || "强制停止失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "强制停止失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "进程已停止")
  }

  const exportLogs = async () => {
    await handleAction("exportLogs", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/export-logs`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "导出日志失败")
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
    }, "日志已导出")
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
