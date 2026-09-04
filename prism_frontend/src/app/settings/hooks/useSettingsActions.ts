"use client"

import { useCallback, useEffect, useState } from "react"
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
  setAutomationRuntime: boolean
  setPlatformBrowser: boolean
  setPlatformProxy: boolean
  installPatchright: boolean
  uninstallPatchright: boolean
  installChromium: boolean
  installFirefox: boolean
  uninstallChromium: boolean
  uninstallFirefox: boolean
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
  automation_worker?: ServiceStatus
  celery_worker?: ServiceStatus
  hermes_gateway?: ServiceStatus
  hermes_dashboard?: ServiceStatus
  hermes_webui?: ServiceStatus
  [key: string]: ServiceStatus | undefined
}

interface RuntimePackageInfo {
  installed: boolean
  version?: string | null
  error?: string | null
}

interface BrowserAssetInfo {
  installed: boolean
  path?: string | null
  version?: string | null
  uninstallable?: boolean
  required?: boolean
}

interface BrowserRuntimeInfo {
  pythonPath?: string
  browsersPath?: string
  preferredRuntime?: "patchright"
  activeRuntime?: string | null
  runtimes?: {
    patchright?: RuntimePackageInfo
  }
  browsers?: {
    chromium?: BrowserAssetInfo
    firefox?: BrowserAssetInfo
  }
}

interface RuntimeSettings {
  browserHeadless: boolean
  automationRuntime?: "patchright"
  browserBackendDefault?: "patchright" | "persona"
  platformBrowserPreferences?: Partial<Record<PlatformBrowserKey, PlatformBrowserChoice>>
  platformProxyPreferences?: Partial<Record<PlatformProxyKey, PlatformProxyChoice>>
}

interface AppInfo {
  version?: string
  name?: string
  isPackaged?: boolean
  resourcesPath?: string
  automationBrowserPath?: string
  runtimeSettings?: RuntimeSettings
  browserRuntimeInfo?: BrowserRuntimeInfo
}

export type PlatformBrowserKey = "douyin" | "kuaishou" | "xiaohongshu" | "channels" | "bilibili"
export type PlatformBrowserChoice = "auto" | "chromium" | "firefox"
export type PlatformProxyKey = "douyin" | "kuaishou" | "xiaohongshu" | "channels" | "bilibili"
export type PlatformProxyChoice = "direct" | "inherit"

const DEFAULT_PLATFORM_BROWSER_PREFERENCES: Record<PlatformBrowserKey, PlatformBrowserChoice> = {
  douyin: "chromium",
  kuaishou: "chromium",
  xiaohongshu: "chromium",
  channels: "chromium",
  bilibili: "chromium",
}

const DEFAULT_PLATFORM_PROXY_PREFERENCES: Record<PlatformProxyKey, PlatformProxyChoice> = {
  douyin: "direct",
  kuaishou: "direct",
  xiaohongshu: "direct",
  channels: "direct",
  bilibili: "direct",
}

const isElectron = typeof window !== "undefined" && Boolean((window as any).electronAPI)

export function useSettingsActions() {
  const { toast } = useToast()
  const apiBase = API_ENDPOINTS.base
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
    setAutomationRuntime: false,
    setPlatformBrowser: false,
    setPlatformProxy: false,
    installPatchright: false,
    uninstallPatchright: false,
    installChromium: false,
    installFirefox: false,
    uninstallChromium: false,
    uninstallFirefox: false,
  })
  const [status, setStatus] = useState<RuntimeStatus | null>(null)
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null)

  const setLoadingState = (key: keyof LoadingState, value: boolean) => {
    setLoading((prev) => ({ ...prev, [key]: value }))
  }

  const updateAppInfo = useCallback((next: Partial<AppInfo>) => {
    setAppInfo((prev) => {
      const previousRuntimeSettings = prev?.runtimeSettings
      const incomingRuntimeSettings = next.runtimeSettings
      const runtimeSettings =
        incomingRuntimeSettings || previousRuntimeSettings
          ? {
              browserHeadless:
                incomingRuntimeSettings?.browserHeadless ??
                previousRuntimeSettings?.browserHeadless ??
                true,
              automationRuntime:
                incomingRuntimeSettings?.automationRuntime ??
                previousRuntimeSettings?.automationRuntime,
              browserBackendDefault:
                incomingRuntimeSettings?.browserBackendDefault ??
                previousRuntimeSettings?.browserBackendDefault ??
                "patchright",
              platformBrowserPreferences: {
                ...DEFAULT_PLATFORM_BROWSER_PREFERENCES,
                ...(previousRuntimeSettings?.platformBrowserPreferences ?? {}),
                ...(incomingRuntimeSettings?.platformBrowserPreferences ?? {}),
              },
              platformProxyPreferences: {
                ...DEFAULT_PLATFORM_PROXY_PREFERENCES,
                ...(previousRuntimeSettings?.platformProxyPreferences ?? {}),
                ...(incomingRuntimeSettings?.platformProxyPreferences ?? {}),
              },
            }
          : undefined

      return {
        ...(prev ?? {}),
        ...next,
        ...(runtimeSettings ? { runtimeSettings } : {}),
      }
    })
  }, [])

  const syncBrowserRuntimeInfo = useCallback((browserRuntimeInfo: BrowserRuntimeInfo | null | undefined) => {
    if (!browserRuntimeInfo) {
      return
    }

    updateAppInfo({
      automationBrowserPath: browserRuntimeInfo.browsersPath,
      browserRuntimeInfo,
    })
  }, [updateAppInfo])

  const loadBrowserRuntimeInfo = useCallback(async (): Promise<BrowserRuntimeInfo | null> => {
    if (isElectron) {
      const electron = (window as any).electronAPI
      if (electron.browserRuntime?.getStatus) {
        const result = await electron.browserRuntime.getStatus()
        if (!result?.success) {
          throw new Error(result?.error || "\u83b7\u53d6\u6d4f\u89c8\u5668\u8fd0\u884c\u65f6\u72b6\u6001\u5931\u8d25")
        }
        return result.browserRuntimeInfo ?? null
      }

      if (electron.app?.getInfo) {
        const info = await electron.app.getInfo()
        return info?.browserRuntimeInfo ?? null
      }

      return null
    }

    const response = await fetch(`${apiBase}/api/v1/system/browser-runtime/status`)
    const data = await response.json().catch(() => ({}))
    if (!response.ok || data?.success === false) {
      throw new Error(data?.detail || data?.error || "\u83b7\u53d6\u6d4f\u89c8\u5668\u8fd0\u884c\u65f6\u72b6\u6001\u5931\u8d25")
    }
    return data?.browserRuntimeInfo ?? null
  }, [apiBase])

  const installBrowserRuntimeTarget = async (
    target: "patchright" | "chromium" | "firefox"
  ) => {
    if (isElectron) {
      const electron = (window as any).electronAPI
      if (electron.browserRuntime?.install) {
        return await electron.browserRuntime.install(target)
      }
    }

    const response = await fetch(`${apiBase}/api/v1/system/browser-runtime/install/${target}`, {
      method: "POST",
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || data?.error || `${target} \u5b89\u88c5\u5931\u8d25`)
    }
    return data
  }

  const uninstallBrowserRuntimeTarget = async (
    target: "patchright" | "chromium" | "firefox"
  ) => {
    if (isElectron) {
      const electron = (window as any).electronAPI
      if (electron.browserRuntime?.uninstall) {
        return await electron.browserRuntime.uninstall(target)
      }
    }

    const response = await fetch(`${apiBase}/api/v1/system/browser-runtime/uninstall/${target}`, {
      method: "POST",
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || data?.error || `${target} 卸载失败`)
    }
    return data
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
        title: "\u64cd\u4f5c\u6210\u529f",
        description: successMessage,
      })
    } catch (error: any) {
      toast({
        title: "\u64cd\u4f5c\u5931\u8d25",
        description: error.message || "\u8bf7\u6c42\u5931\u8d25",
        variant: "destructive",
      })
      throw error
    } finally {
      setLoadingState(key, false)
    }
  }

  const refreshStatus = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    setLoadingState("refreshStatus", true)
    try {
      if (isElectron) {
        const electron = (window as any).electronAPI
        let nextStatus = null
        if (electron.supervisor?.getStatus) {
          try {
            nextStatus = await electron.supervisor.getStatus()
          } catch {
            nextStatus = await electron.system.getStatus()
          }
        } else {
          nextStatus = await electron.system.getStatus()
        }
        setStatus(nextStatus ?? null)
        if (electron.app?.getInfo) {
          updateAppInfo(await electron.app.getInfo())
        }
      } else {
        setStatus(null)
        // web 版：从后端读取无头模式设置
        try {
          const res = await fetch(`${apiBase}/api/v1/system/browser-headless`, { cache: "no-store" })
          if (res.ok) {
            const payload = await res.json()
            if (typeof payload?.headless === "boolean") {
              updateAppInfo({ runtimeSettings: { browserHeadless: payload.headless } })
            }
          }
        } catch (e) {
          // 忽略：无头模式读不到时保持默认
        }
      }

      syncBrowserRuntimeInfo(await loadBrowserRuntimeInfo())

      if (!silent) {
        toast({
          title: "\u72b6\u6001\u5df2\u5237\u65b0",
          description: "\u8fd0\u884c\u65f6\u4fe1\u606f\u5df2\u66f4\u65b0",
        })
      }
    } catch (error: any) {
      if (!silent) {
        toast({
          title: "\u5237\u65b0\u5931\u8d25",
          description: error.message || "\u65e0\u6cd5\u52a0\u8f7d\u8fd0\u884c\u65f6\u72b6\u6001",
          variant: "destructive",
        })
      }
      throw error
    } finally {
      setLoadingState("refreshStatus", false)
    }
  }, [loadBrowserRuntimeInfo, syncBrowserRuntimeInfo, toast, updateAppInfo])

  useEffect(() => {
    void refreshStatus({ silent: true })
  }, [refreshStatus])

  const restartAll = async () => {
    await handleAction("restartAll", async () => {
      if (isElectron) {
        const result = await (window as any).electronAPI.system.restartAll()
        if (!result.success) {
          throw new Error(result.error || "服务重启失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "服务重启失败")
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
          throw new Error(result.error || "停止服务失败")
        }
      } else {
        const response = await fetch(`${apiBase}/api/v1/system/supervisor/stop`, {
          method: "POST",
        })
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.detail || "停止服务失败")
        }
      }
      await refreshStatus({ silent: true })
    }, "所有服务已停止")
  }

  const setBrowserHeadless = async (browserHeadless: boolean) => {
    await handleAction("setBrowserHeadless", async () => {
      if (!isElectron) {
        // web 版：调用后端接口写 .env
        const response = await fetch(`${apiBase}/api/v1/system/browser-headless`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ headless: browserHeadless }),
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok || !payload?.success) {
          throw new Error(payload?.detail || payload?.error || "无头模式更新失败")
        }
        updateAppInfo({ runtimeSettings: { browserHeadless: payload.headless ?? browserHeadless } })
        toast({
          title: "设置已保存",
          description: "重启后端后生效",
        })
        return
      }

      const electron = (window as any).electronAPI
      const result = await electron.settings.update({ browserHeadless })
      if (!result.success) {
        throw new Error(result.error || "无头模式更新失败")
      }

      updateAppInfo({
        runtimeSettings: result.settings,
        browserRuntimeInfo: result.browserRuntimeInfo,
      })

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "重启服务失败")
      }

      await refreshStatus({ silent: true })
    }, browserHeadless ? "已启用无头模式" : "已关闭无头模式")
  }

  const setAutomationRuntime = async (automationRuntime: "patchright") => {
    await handleAction("setAutomationRuntime", async () => {
      if (!isElectron) {
        throw new Error("\u9996\u9009\u8fd0\u884c\u65f6\u5207\u6362\u4ec5\u684c\u9762\u7248\u53ef\u7528")
      }

      const electron = (window as any).electronAPI
      const runtimeInstalled = appInfo?.browserRuntimeInfo?.runtimes?.[automationRuntime]?.installed
      if (!runtimeInstalled) {
        const installResult = await installBrowserRuntimeTarget(automationRuntime)
        if (!installResult.success) {
          throw new Error(installResult.error || `${automationRuntime} \u5b89\u88c5\u5931\u8d25`)
        }
        syncBrowserRuntimeInfo(installResult.browserRuntimeInfo)
      }

      const result = await electron.settings.update({ automationRuntime })
      if (!result.success) {
        throw new Error(result.error || "\u8fd0\u884c\u65f6\u5207\u6362\u5931\u8d25")
      }

      updateAppInfo({
        runtimeSettings: result.settings,
        browserRuntimeInfo: result.browserRuntimeInfo,
      })

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "\u670d\u52a1\u91cd\u542f\u5931\u8d25")
      }

      await refreshStatus({ silent: true })
    }, "\u5df2\u542f\u7528 Patchright")
  }

  const setBrowserBackendDefault = async (browserBackendDefault: "patchright" | "persona") => {
    await handleAction("setAutomationRuntime", async () => {
      if (!isElectron) throw new Error("默认浏览器后端切换仅桌面版可用")
      const electron = (window as any).electronAPI
      const result = await electron.settings.update({ browserBackendDefault })
      if (!result.success) throw new Error(result.error || "默认浏览器后端切换失败")
      updateAppInfo({ runtimeSettings: result.settings })
      await refreshStatus({ silent: true })
    }, `已切换为 ${browserBackendDefault}；新浏览器会话立即生效`)
  }

  const setPlatformBrowserPreference = async (
    platform: PlatformBrowserKey,
    browser: PlatformBrowserChoice
  ) => {
    await handleAction("setPlatformBrowser", async () => {
      if (!isElectron) {
        throw new Error("平台浏览器切换仅桌面版可用")
      }

      const currentPreferences = {
        ...DEFAULT_PLATFORM_BROWSER_PREFERENCES,
        ...(appInfo?.runtimeSettings?.platformBrowserPreferences ?? {}),
      }

      const electron = (window as any).electronAPI
      const result = await electron.settings.update({
        platformBrowserPreferences: {
          ...currentPreferences,
          [platform]: browser,
        },
      })
      if (!result.success) {
        throw new Error(result.error || "平台浏览器设置更新失败")
      }

      updateAppInfo({
        runtimeSettings: result.settings,
        browserRuntimeInfo: result.browserRuntimeInfo,
      })

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "服务重启失败")
      }

      await refreshStatus({ silent: true })
    }, "平台浏览器设置已更新，服务已重启")
  }

  const setPlatformProxyPreference = async (
    platform: PlatformProxyKey,
    mode: PlatformProxyChoice
  ) => {
    await handleAction("setPlatformProxy", async () => {
      if (!isElectron) {
        throw new Error("平台代理切换仅桌面版可用")
      }

      const currentPreferences = {
        ...DEFAULT_PLATFORM_PROXY_PREFERENCES,
        ...(appInfo?.runtimeSettings?.platformProxyPreferences ?? {}),
      }

      const electron = (window as any).electronAPI
      const result = await electron.settings.update({
        platformProxyPreferences: {
          ...currentPreferences,
          [platform]: mode,
        },
      })
      if (!result.success) {
        throw new Error(result.error || "平台代理设置更新失败")
      }

      updateAppInfo({
        runtimeSettings: result.settings,
        browserRuntimeInfo: result.browserRuntimeInfo,
      })

      const restartResult = await electron.system.restartAll()
      if (!restartResult.success) {
        throw new Error(restartResult.error || "服务重启失败")
      }

      await refreshStatus({ silent: true })
    }, "平台代理设置已更新，服务已重启")
  }

  const restartServicesAfterBrowserAssetChange = async () => {
    const restartViaBackend = async () => {
      const response = await fetch(`${apiBase}/api/v1/system/supervisor/restart`, {
        method: "POST",
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data?.detail || data?.error || "服务重启失败")
      }
      if (data?.status === "error") {
        throw new Error(data?.message || "服务重启失败")
      }
      if (data?.status === "unavailable") {
        throw new Error(data?.message || "服务重启暂不可用")
      }
      return true
    }

    if (isElectron) {
      const electron = (window as any).electronAPI
      if (electron.system?.restartAll) {
        const restartResult = await electron.system.restartAll()
        if (restartResult.success) {
          return true
        }
      }
    }

    try {
      return await restartViaBackend()
    } catch (error: any) {
      toast({
        title: "浏览器资源已变更",
        description: `${error?.message || "服务重启失败"}，请手动重启服务后再使用。`,
        variant: "destructive",
      })
      return false
    }
  }

  const installBrowserAsset = async (
    key: "installPatchright" | "installChromium" | "installFirefox",
    target: "patchright" | "chromium" | "firefox",
    label: string
  ) => {
    await handleAction(key, async () => {
      const result = await installBrowserRuntimeTarget(target)
      if (!result.success) {
        throw new Error(result.error || `${label} \u5b89\u88c5\u5931\u8d25`)
      }

      syncBrowserRuntimeInfo(result.browserRuntimeInfo)

      let restartSucceeded = true
      if (target === "patchright" || isElectron) {
        restartSucceeded = await restartServicesAfterBrowserAssetChange()
      }

      if (restartSucceeded) {
        await refreshStatus({ silent: true })
      } else {
        try {
          await refreshStatus({ silent: true })
        } catch {
          // Services may still be restarting after a timeout; keep install successful.
        }
      }
    }, `${label} \u5df2\u5b89\u88c5`)
  }

  const installPatchright = async () => {
    await installBrowserAsset("installPatchright", "patchright", "Patchright")
  }

  const installChromium = async () => {
    await installBrowserAsset("installChromium", "chromium", "Hibbiki Chromium")
  }

  const installFirefox = async () => {
    await installBrowserAsset("installFirefox", "firefox", "Firefox")
  }

  const uninstallBrowserAsset = async (
    key: "uninstallPatchright" | "uninstallChromium" | "uninstallFirefox",
    target: "patchright" | "chromium" | "firefox",
    label: string
  ) => {
    await handleAction(key, async () => {
      const result = await uninstallBrowserRuntimeTarget(target)
      if (!result.success) {
        throw new Error(result.error || `${label} 卸载失败`)
      }

      syncBrowserRuntimeInfo(result.browserRuntimeInfo)

      const restartSucceeded = (target === "patchright" || isElectron)
        ? await restartServicesAfterBrowserAssetChange()
        : true

      if (restartSucceeded) {
        await refreshStatus({ silent: true })
      } else {
        try {
          await refreshStatus({ silent: true })
        } catch {
          // Services may still be restarting after a timeout; keep uninstall successful.
        }
      }
    }, `${label} 已卸载`)
  }

  const uninstallChromium = async () => {
    await uninstallBrowserAsset("uninstallChromium", "chromium", "Hibbiki Chromium")
  }

  const uninstallFirefox = async () => {
    await uninstallBrowserAsset("uninstallFirefox", "firefox", "Firefox")
  }

  const uninstallPatchright = async () => {
    await uninstallBrowserAsset("uninstallPatchright", "patchright", "Patchright")
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
    }, "账号与 Cookie 已清理")
  }

  const clearBrowser = async () => {
    await handleAction("clearBrowser", async () => {
      const response = await fetch(`${apiBase}/api/v1/system/clear-browser`, {
        method: "POST",
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "清理浏览器数据失败")
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
        throw new Error(`发现问题:\n${data.issues.join("\n")}`)
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
    }, "相关进程已停止")
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
      a.download = `prism-logs-${new Date().toISOString().split("T")[0]}.zip`
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
    isElectronApp: isElectron,
    refreshStatus,
    restartAll,
    restartBackend,
    restartFrontend,
    stopAll,
    setBrowserHeadless,
    setAutomationRuntime,
    setBrowserBackendDefault,
    setPlatformBrowserPreference,
    setPlatformProxyPreference,
    installPatchright,
    uninstallPatchright,
    installChromium,
    installFirefox,
    uninstallChromium,
    uninstallFirefox,
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
