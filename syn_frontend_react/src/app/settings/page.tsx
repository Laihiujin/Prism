"use client"

import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { HermesProviderCard } from "@/components/settings/hermes-provider-card"
import {
  Activity,
  AlertTriangle,
  Cookie,
  Database,
  Download,
  FileText,
  Globe,
  HardDrive,
  Loader2,
  Power,
  RefreshCw,
  RotateCcw,
  Trash2,
  Video,
} from "lucide-react"
import { ConfirmModal } from "./components/ConfirmModal"
import { ActionRow } from "./components/ActionRow"
import {
  type PlatformBrowserChoice,
  type PlatformBrowserKey,
  useSettingsActions,
} from "./hooks/useSettingsActions"

const statusLabels: Record<string, string> = {
  frontend: "前端",
  backend: "后端",
  supervisor: "调度器",
  playwright_worker: "Playwright Worker",
  celery_worker: "Celery Worker",
  hermes_gateway: "Hermes Gateway",
  hermes_dashboard: "Hermes Dashboard",
  hermes_webui: "Hermes WebUI",
}

const platformBrowserRows: Array<{
  key: PlatformBrowserKey
  label: string
  description: string
}> = [
  { key: "douyin", label: "抖音", description: "创作中心、登录校验和发布链路" },
  { key: "kuaishou", label: "快手", description: "账号登录、Cookie 复用和上传链路" },
  { key: "xiaohongshu", label: "小红书", description: "创作者中心与内容发布流程" },
  { key: "channels", label: "视频号", description: "微信视频号 / Channels / Tencent 统一配置" },
  { key: "bilibili", label: "B站", description: "创作中心与稿件发布流程" },
]

const platformBrowserLabels: Record<PlatformBrowserChoice, string> = {
  auto: "自动",
  chromium: "Chromium",
  firefox: "Firefox",
}

const defaultPlatformBrowserPreferences: Record<PlatformBrowserKey, PlatformBrowserChoice> = {
  douyin: "chromium",
  kuaishou: "chromium",
  xiaohongshu: "chromium",
  channels: "chromium",
  bilibili: "chromium",
}

export default function SettingsPage() {
  const { toast } = useToast()
  const {
    appInfo,
    status,
    refreshStatus,
    restartAll,
    restartBackend,
    restartFrontend,
    stopAll,
    setBrowserHeadless,
    setAutomationRuntime,
    installPatchright,
    installPlaywright,
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
    setPlatformBrowserPreference,
    loading,
    isElectronApp,
  } = useSettingsActions()

  const [confirmModal, setConfirmModal] = useState<{
    open: boolean
    title: string
    description: string
    confirmText?: string
    requireInput?: boolean
    onConfirm: () => Promise<void> | void
    variant?: "default" | "danger"
  }>({
    open: false,
    title: "",
    description: "",
    onConfirm: () => {},
  })

  const handleConfirm = async () => {
    try {
      await confirmModal.onConfirm()
      setConfirmModal((prev) => ({ ...prev, open: false }))
    } catch (error: any) {
      toast({
        title: "操作失败",
        description: error.message || "请求失败",
        variant: "destructive",
      })
    }
  }

  const serviceEntries = Object.entries(status ?? {}).filter(([, value]) => value)
  const browserRuntimeInfo = appInfo?.browserRuntimeInfo
  const currentRuntime =
    appInfo?.runtimeSettings?.automationRuntime ?? browserRuntimeInfo?.preferredRuntime ?? "patchright"
  const browserHeadless = appInfo?.runtimeSettings?.browserHeadless
  const platformBrowserPreferences = {
    ...defaultPlatformBrowserPreferences,
    ...(appInfo?.runtimeSettings?.platformBrowserPreferences ?? {}),
  }
  const getEffectivePlatformBrowser = (platform: PlatformBrowserKey): Exclude<PlatformBrowserChoice, "auto"> => {
    const selected = platformBrowserPreferences[platform]
    if (selected === "firefox") {
      return "firefox"
    }
    if (selected === "auto") {
      return defaultPlatformBrowserPreferences[platform] === "firefox" ? "firefox" : "chromium"
    }
    return "chromium"
  }
  const runtimeModeLabel = !isElectronApp
    ? "网页版"
    : appInfo == null
      ? "读取中"
      : appInfo.isPackaged
        ? "正式版"
        : "开发版"

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="系统设置"
        description="管理桌面运行时、服务进程和本地数据"
        actions={
          <Button
            onClick={() => void refreshStatus()}
            disabled={loading.refreshStatus}
            variant="secondary"
            className="bg-white/10"
          >
            {loading.refreshStatus ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                刷新中
              </>
            ) : (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                刷新状态
              </>
            )}
          </Button>
        }
      />

      <div className="mx-auto max-w-5xl space-y-6">
        <HermesProviderCard />

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              运行概览
            </CardTitle>
            <CardDescription className="text-white/60">
              查看打包运行时、浏览器路径和服务健康状态。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">版本</div>
                <div className="mt-2 text-lg font-semibold text-white">{appInfo?.version || "-"}</div>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">模式</div>
                <div className="mt-2 text-lg font-semibold text-white">{runtimeModeLabel}</div>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">托盘退出</div>
                <div className="mt-2 text-lg font-semibold text-white">停止所有受管进程</div>
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/50">Playwright 浏览器路径</div>
              <div className="mt-2 break-all font-mono text-xs text-white/80">
                {appInfo?.playwrightBrowserPath || "-"}
              </div>
            </div>

            <div className="flex items-center justify-between gap-4 rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="min-w-0">
                <div className="font-medium text-white">Chromium 无头模式</div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {loading.setBrowserHeadless && <Loader2 className="h-4 w-4 animate-spin text-white/60" />}
                <Switch
                  checked={browserHeadless === true}
                  disabled={loading.setBrowserHeadless || typeof browserHeadless !== "boolean"}
                  onCheckedChange={(checked) => void setBrowserHeadless(checked)}
                  aria-label="切换无头模式"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {serviceEntries.length > 0 ? (
                serviceEntries.map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-white/10 bg-black/30 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-white">{statusLabels[key] || key}</div>
                      <Badge
                        variant="outline"
                        className={
                          value?.running
                            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                            : "border-white/15 bg-white/5 text-white/60"
                        }
                      >
                        {value?.running ? "运行中" : "已停止"}
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-white/60">
                      <div>进程号: {value?.pid ?? "-"}</div>
                      <div>外部进程: {value?.external ? "是" : "否"}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-white/10 bg-black/20 p-4 text-sm text-white/60">
                  目前还没有运行状态。
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => window.open("/api/v1/system/logs", "_blank")}
                variant="secondary"
                className="bg-white/10"
              >
                <FileText className="mr-2 h-4 w-4" />
                查看日志
              </Button>
              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "退出应用",
                    description: "这会关闭桌面应用，移除托盘图标，并停止所有受管本地进程。",
                    onConfirm: quitApp,
                    variant: "danger",
                  })
                }
                disabled={loading.quitApp}
                variant="destructive"
              >
                {loading.quitApp ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    退出中
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    退出并停止所有进程
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5 text-primary" />
              {"\u6d4f\u89c8\u5668\u7ec4\u4ef6"}
            </CardTitle>
            <CardDescription className="text-white/60">
              {"\u7edf\u4e00\u67e5\u770b\u548c\u7ba1\u7406 Chromium\u3001Firefox\u3001Patchright\u3001Playwright \u4ee5\u53ca\u672c\u5730\u7f13\u5b58\u76ee\u5f55\u3002"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/50">{"\u5f53\u524d Python \u73af\u5883"}</div>
              <div className="mt-2 break-all font-mono text-xs text-white/80">
                {browserRuntimeInfo?.pythonPath || "\u68c0\u6d4b\u4e2d..."}
              </div>
              <div className="mt-3 text-sm text-white/50">{"\u6d4f\u89c8\u5668\u7f13\u5b58\u76ee\u5f55"}</div>
              <div className="mt-2 break-all font-mono text-xs text-white/80">
                {browserRuntimeInfo?.browsersPath || appInfo?.playwrightBrowserPath || "\u68c0\u6d4b\u4e2d..."}
              </div>
              {!isElectronApp && (
                <div className="mt-3 text-xs text-amber-300/80">
                  {"\u5f53\u524d\u4e3a\u7f51\u9875\u6a21\u5f0f\uff1a\u53ef\u67e5\u770b\u5e76\u5b89\u88c5\u7ec4\u4ef6\uff0c\u4f46\u9996\u9009\u8fd0\u884c\u65f6\u5207\u6362\u4ec5\u684c\u9762\u7248\u53ef\u7528\u3002"}
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/30 p-4">
              <div>
                <div className="text-sm text-white/50">{"\u9996\u9009\u8fd0\u884c\u65f6"}</div>
                <div className="mt-1 text-xs text-white/60">
                  {"\u8fd9\u4e2a\u9009\u62e9\u53ea\u51b3\u5b9a\u81ea\u52a8\u5316\u9ed8\u8ba4\u8d70 Patchright \u8fd8\u662f Playwright\u3002"}
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant={currentRuntime === "patchright" ? "default" : "secondary"}
                  className={currentRuntime === "patchright" ? "" : "bg-white/10"}
                  disabled={loading.setAutomationRuntime || !isElectronApp}
                  onClick={() => void setAutomationRuntime("patchright")}
                >
                  {loading.setAutomationRuntime && currentRuntime === "patchright" && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Patchright
                </Button>
                <Button
                  variant={currentRuntime === "playwright" ? "default" : "secondary"}
                  className={currentRuntime === "playwright" ? "" : "bg-white/10"}
                  disabled={loading.setAutomationRuntime || !isElectronApp}
                  onClick={() => void setAutomationRuntime("playwright")}
                >
                  {loading.setAutomationRuntime && currentRuntime === "playwright" && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Playwright
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-black/20 p-4 md:col-span-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 font-medium text-white">
                      <Globe className="h-4 w-4 text-primary" />
                      平台浏览器
                    </div>
                    <div className="mt-2 text-xs text-white/60">
                      为 5 个平台分别指定默认浏览器。新设置会用于后续新开的登录、创作中心和自动化上下文。
                    </div>
                  </div>
                  {loading.setPlatformBrowser && <Loader2 className="h-4 w-4 animate-spin text-white/60" />}
                </div>
                <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
                  {platformBrowserRows.map((platform) => (
                    <div
                      key={platform.key}
                      className="rounded-lg border border-white/10 bg-black/30 p-4"
                    >
                      <div className="text-sm font-medium text-white">{platform.label}</div>
                      <div className="mt-1 text-xs text-white/55">{platform.description}</div>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-white/65">
                          已设置：{platformBrowserLabels[platformBrowserPreferences[platform.key]]}
                        </span>
                        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-emerald-300">
                          当前生效：{platformBrowserLabels[getEffectivePlatformBrowser(platform.key)]}
                        </span>
                      </div>
                      <div className="mt-4">
                        <Select
                          value={platformBrowserPreferences[platform.key]}
                          onValueChange={(value) =>
                            void setPlatformBrowserPreference(
                              platform.key,
                              value as PlatformBrowserChoice
                            )
                          }
                          disabled={loading.setPlatformBrowser || !isElectronApp}
                        >
                          <SelectTrigger className="h-10 rounded-lg border-white/10 bg-white/5">
                            <SelectValue placeholder="选择浏览器" />
                          </SelectTrigger>
                          <SelectContent>
                            {(["auto", "chromium", "firefox"] as PlatformBrowserChoice[]).map((option) => (
                              <SelectItem key={option} value={option}>
                                {platformBrowserLabels[option]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Patchright</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.runtimes?.patchright?.installed
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-white/15 bg-white/5 text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.runtimes?.patchright?.installed
                      ? `\u5df2\u5b89\u88c5 ${browserRuntimeInfo?.runtimes?.patchright?.version || ""}`.trim()
                      : "\u672a\u5b89\u88c5"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.activeRuntime === "patchright"
                    ? "\u5f53\u524d\u5df2\u542f\u7528"
                    : browserRuntimeInfo?.runtimes?.patchright?.error || "\u63a8\u8350\u7528\u4e8e Chromium \u81ea\u52a8\u5316"}
                </div>
                <Button
                  onClick={() => void installPatchright()}
                  disabled={loading.installPatchright}
                  variant="secondary"
                  className="mt-4 w-full bg-white/10"
                >
                  {loading.installPatchright ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {"\u5b89\u88c5\u4e2d..."}
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      {browserRuntimeInfo?.runtimes?.patchright?.installed
                        ? "\u91cd\u88c5 Patchright"
                        : "\u5b89\u88c5 Patchright"}
                    </>
                  )}
                </Button>
              </div>

              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Playwright</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.runtimes?.playwright?.installed
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-white/15 bg-white/5 text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.runtimes?.playwright?.installed
                      ? `\u5df2\u5b89\u88c5 ${browserRuntimeInfo?.runtimes?.playwright?.version || ""}`.trim()
                      : "\u672a\u5b89\u88c5"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.activeRuntime === "playwright"
                    ? "\u5f53\u524d\u5df2\u542f\u7528"
                    : "\u53ef\u4f5c\u4e3a\u517c\u5bb9\u540e\u5907\u8fd0\u884c\u65f6"}
                </div>
                <Button
                  onClick={() => void installPlaywright()}
                  disabled={loading.installPlaywright}
                  variant="secondary"
                  className="mt-4 w-full bg-white/10"
                >
                  {loading.installPlaywright ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {"\u5b89\u88c5\u4e2d..."}
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      {browserRuntimeInfo?.runtimes?.playwright?.installed
                        ? "\u91cd\u88c5 Playwright"
                        : "\u5b89\u88c5 Playwright"}
                    </>
                  )}
                </Button>
              </div>

              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Chromium</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.browsers?.chromium?.installed
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-white/15 bg-white/5 text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.browsers?.chromium?.installed ? "\u5df2\u5b89\u88c5" : "\u672a\u5b89\u88c5"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.browsers?.chromium?.version
                    ? `\u5f53\u524d\u7248\u672c: ${browserRuntimeInfo?.browsers?.chromium?.version}`
                    : "\u5b89\u88c5\u540e\u4f1a\u5199\u5165 browsers/chromium/hibbiki-* \u76ee\u5f55\u3002"}
                </div>
                <div className="mt-3 break-all font-mono text-xs text-white/70">
                  {browserRuntimeInfo?.browsers?.chromium?.path || "\u68c0\u6d4b\u5230\u540e\u4f1a\u5728\u8fd9\u91cc\u663e\u793a\u5b9e\u9645\u53ef\u6267\u884c\u6587\u4ef6\u8def\u5f84\u3002"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installChromium()}
                    disabled={loading.installChromium}
                    variant="secondary"
                    className="flex-1 bg-white/10"
                  >
                    {loading.installChromium ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {"\u5b89\u88c5\u4e2d..."}
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.browsers?.chromium?.installed
                          ? "\u91cd\u88c5 Chromium"
                          : "\u4e0b\u8f7d Chromium"}
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => void uninstallChromium()}
                    disabled={loading.uninstallChromium || !browserRuntimeInfo?.browsers?.chromium?.installed}
                    variant="secondary"
                    className="border border-white/10 bg-white/5 text-white/40"
                  >
                    {loading.uninstallChromium ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <Trash2 className="mr-2 h-4 w-4" />
                        卸载
                      </>
                    )}
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Firefox</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.browsers?.firefox?.installed
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-white/15 bg-white/5 text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.browsers?.firefox?.installed ? "\u5df2\u5b89\u88c5" : "\u672a\u5b89\u88c5"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.browsers?.firefox?.version
                    ? `\u5f53\u524d\u7248\u672c: ${browserRuntimeInfo?.browsers?.firefox?.version}`
                    : "\u5b89\u88c5\u540e\u4f1a\u5199\u5165\u9879\u76ee\u672c\u5730 browsers \u76ee\u5f55\u3002"}
                </div>
                <div className="mt-3 break-all font-mono text-xs text-white/70">
                  {browserRuntimeInfo?.browsers?.firefox?.path || "\u68c0\u6d4b\u5230\u540e\u4f1a\u5728\u8fd9\u91cc\u663e\u793a\u5b9e\u9645\u53ef\u6267\u884c\u6587\u4ef6\u8def\u5f84\u3002"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installFirefox()}
                    disabled={loading.installFirefox}
                    variant="secondary"
                    className="flex-1 bg-white/10"
                  >
                    {loading.installFirefox ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {"\u5b89\u88c5\u4e2d..."}
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.browsers?.firefox?.installed
                          ? "\u91cd\u88c5 Firefox"
                          : "\u4e0b\u8f7d Firefox"}
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => void uninstallFirefox()}
                    disabled={
                      loading.uninstallFirefox ||
                      !browserRuntimeInfo?.browsers?.firefox?.installed ||
                      browserRuntimeInfo?.browsers?.firefox?.uninstallable === false
                    }
                    variant="secondary"
                    className="border border-white/10 bg-white/5 text-white/40"
                  >
                    {loading.uninstallFirefox ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        卸载中...
                      </>
                    ) : (
                      <>
                        <Trash2 className="mr-2 h-4 w-4" />
                        卸载
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              进程控制
            </CardTitle>
            <CardDescription className="text-white/60">
              对桌面运行时常用的重启和停止操作。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "重启所有服务",
                    description: "这会重启前端、后端和各个工作进程。打包模式下会走调度器的受管重启流程。",
                    onConfirm: restartAll,
                  })
                }
                disabled={loading.restartAll}
                className="w-full"
              >
                {loading.restartAll ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    重启中
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    重启所有服务
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "重启后端",
                    description: "用于恢复本地 API 和登录链路。打包模式下会调用调度器的后端重启接口。",
                    onConfirm: restartBackend,
                  })
                }
                disabled={loading.restartBackend}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.restartBackend ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    重启中
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    重启后端
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "重启前端",
                    description: "这会重新加载内置应用服务，但不会关闭桌面壳。",
                    onConfirm: restartFrontend,
                  })
                }
                disabled={loading.restartFrontend}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.restartFrontend ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    重启中
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    重启前端
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "停止所有服务",
                    description: "这会停止前端、后端、工作进程和调度器管理的服务。桌面壳仍可停留在托盘中。",
                    onConfirm: stopAll,
                    variant: "danger",
                  })
                }
                disabled={loading.stopAll}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.stopAll ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    停止中
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    停止所有服务
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              数据清理
            </CardTitle>
            <CardDescription className="text-white/60">
              清理本地缓存、登录数据和生成的业务数据。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <ActionRow
              icon={HardDrive}
              label="清理素材"
              description="删除本地素材文件和记录"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "清理素材",
                  description: "这会删除本地素材文件及其记录，操作不可撤销。",
                  onConfirm: clearMaterials,
                  variant: "danger",
                })
              }
              loading={loading.clearMaterials}
            />

            <ActionRow
              icon={Cookie}
              label="清理账号和 Cookie"
              description="删除本地登录状态，需要重新绑定或重新登录"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "清理账号和 Cookie",
                  description: "这会删除本地账号数据、Cookie 和登录令牌。",
                  onConfirm: clearAccounts,
                  variant: "danger",
                })
              }
              loading={loading.clearAccounts}
            />

            <ActionRow
              icon={Trash2}
              label="清理浏览器数据"
              description="删除内置浏览器缓存、历史记录和临时文件"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "清理浏览器数据",
                  description: "这会清除 Electron 浏览器缓存及相关临时文件。",
                  onConfirm: clearBrowser,
                  variant: "danger",
                })
              }
              loading={loading.clearBrowser}
            />

            <ActionRow
              icon={Database}
              label="清理全部缓存"
              description="清空应用缓存、临时目录和 API 缓存"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "清理全部缓存",
                  description: "这会清除应用缓存和临时文件，便于重新启动。",
                  onConfirm: clearCache,
                  variant: "danger",
                })
              }
              loading={loading.clearCache}
            />

            <ActionRow
              icon={Video}
              label="清理视频数据"
              description="删除本地视频、分析数据和历史记录"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "清理视频数据",
                  description: "这会删除本地视频文件和分析结果，操作不可撤销。",
                  onConfirm: clearVideoData,
                  variant: "danger",
                })
              }
              loading={loading.clearVideoData}
            />
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              应急工具
            </CardTitle>
            <CardDescription className="text-white/60">
              当桌面运行时不稳定时，可以快速查看诊断和处理手段。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={async () => {
                  try {
                    await runSelfCheck()
                  } catch (error: any) {
                    toast({
                      title: "自检失败",
                      description: error.message,
                      variant: "destructive",
                    })
                  }
                }}
                disabled={loading.runSelfCheck}
                variant="secondary"
                className="bg-white/10"
              >
                {loading.runSelfCheck ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    检查中
                  </>
                ) : (
                  <>
                    <Activity className="mr-2 h-4 w-4" />
                    运行自检
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "强制停止相关进程",
                    description: "这会立即终止本地运行时进程。输入 CONFIRM 继续。",
                    requireInput: true,
                    confirmText: "CONFIRM",
                    onConfirm: forceKillProcesses,
                    variant: "danger",
                  })
                }
                disabled={loading.forceKill}
                variant="destructive"
              >
                {loading.forceKill ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    停止中
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    强制停止进程
                  </>
                )}
              </Button>

              <Button
                onClick={async () => {
                  try {
                    await exportLogs()
                  } catch (error: any) {
                    toast({
                      title: "导出失败",
                      description: error.message,
                      variant: "destructive",
                    })
                  }
                }}
                disabled={loading.exportLogs}
                variant="secondary"
                className="bg-white/10"
              >
                {loading.exportLogs ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    导出中
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    导出日志
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <ConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        description={confirmModal.description}
        confirmText={confirmModal.confirmText}
        requireInput={confirmModal.requireInput}
        variant={confirmModal.variant}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
      />
    </div>
  )
}
