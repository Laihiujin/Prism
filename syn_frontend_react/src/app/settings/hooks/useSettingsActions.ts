"use client"

import { useState } from "react"
import { useToast } from "@/components/ui/use-toast"
import { API_ENDPOINTS } from "@/lib/env"

interface LoadingState {
  restartAll: boolean
  restartBackend: boolean
  restartFrontend: boolean
  stopAll: boolean
  clearMaterials: boolean
  clearAccounts: boolean
  clearBrowser: boolean
  clearCache: boolean
  clearVideoData: boolean
  runSelfCheck: boolean
  forceKill: boolean
  exportLogs: boolean
}

// 检测是否在 Electron 环境
const isElectron = typeof window !== "undefined" && (window as any).electronAPI

export function useSettingsActions() {
  const { toast } = useToast()
  const apiBase = API_ENDPOINTS.base || "http://localhost:7000"
  const [loading, setLoading] = useState<LoadingState>({
    restartAll: false,
    restartBackend: false,
    restartFrontend: false,
    stopAll: false,
    clearMaterials: false,
    clearAccounts: false,
    clearBrowser: false,
    clearCache: false,
    clearVideoData: false,
    runSelfCheck: false,
    forceKill: false,
    exportLogs: false,
  })

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
        description: error.message || "执行操作失败",
        variant: "destructive",
      })
      throw error
    } finally {
      setLoadingState(key, false)
    }
  }

  // ========== 进程控制操作（使用后端 API） ==========

  const restartAll = async () => {
    await handleAction("restartAll", async () => {
      // 优先使用 Electron IPC（如在 Electron 环境）
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
    }, "所有服务已重启")
  }

  const restartBackend = async () => {
    await handleAction("restartBackend", async () => {
      // 优先使用 Electron IPC（如在 Electron 环境）
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartBackend()
        if (!result.success) {
          throw new Error(result.error || "重启失败")
        }
      } else {
        // 重启 FastAPI 后端
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart/backend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "重启失败")
        }
      }
    }, "后端服务已重启")
  }

  const restartFrontend = async () => {
    await handleAction("restartFrontend", async () => {
      // 优先使用 Electron IPC（如在 Electron 环境）
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartFrontend()
        if (!result.success) {
          throw new Error(result.error || "重启失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/restart-frontend`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "重启失败")
        }
      }
    }, "前端服务已重启")
  }

  const stopAll = async () => {
    await handleAction("stopAll", async () => {
      // 优先使用 Electron IPC（如在 Electron 环境）
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
    }, "所有服务已停止")
  }

  // ========== 数据清理操作（使用后端 API） ==========

  const clearMaterials = async () => {
    await handleAction("clearMaterials", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-materials`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理失败")
      }
    }, "素材数据已清理")
  }

  const clearAccounts = async () => {
    await handleAction("clearAccounts", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-accounts`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理失败")
      }
    }, "账号与 Cookies 已清理")
  }

  const clearBrowser = async () => {
    await handleAction("clearBrowser", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-browser`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理失败")
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
        throw new Error(data.detail || "清理失败")
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
        throw new Error(data.detail || "清理失败")
      }
    }, "视频数据已清理")
  }

  // ========== 紧急操作 ==========

  const runSelfCheck = async () => {
    await handleAction("runSelfCheck", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/self-check`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "自检失败")
      }
      const data = await response.json()

      // 显示详细自检结果
      if (data.status === "warning" && data.issues && data.issues.length > 0) {
        throw new Error(`发现问题:\n${data.issues.join("\n")}`)
      }
    }, "系统自检完成，一切正常")
  }

  const forceKillProcesses = async () => {
    await handleAction("forceKill", async () => {
      // 优先使用 Electron IPC（如在 Electron 环境）
      if (isElectron) {
        const result = await (window as any).electronAPI.system.stopAll()
        if (!result.success) {
          throw new Error(result.error || "终止失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "终止失败")
        }
      }
    }, "进程已强制终止")
  }

  const exportLogs = async () => {
    await handleAction("exportLogs", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/export-logs`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "导出失败")
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
    loading,
    restartAll,
    restartBackend,
    restartFrontend,
    stopAll,
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
