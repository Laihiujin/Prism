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
import { AIServiceProviderCard } from "@/components/settings/ai-service-provider-card"
import { HermesProviderCard } from "@/components/settings/hermes-provider-card"
import {
  Activity,
  AlertTriangle,
  Bot,
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

type SectionKey =
  | "overview"
  | "models"
  | "browsers"
  | "processes"
  | "storage"
  | "safety"

type ConfirmState = {
  open: boolean
  title: string
  description: string
  confirmText?: string
  requireInput?: boolean
  onConfirm: () => Promise<void> | void
  variant?: "default" | "danger"
}

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

const sectionMeta: Array<{
  key: SectionKey
  label: string
  description: string
  icon: typeof Activity
}> = [
  { key: "overview", label: "运行概览", description: "运行时与服务状态", icon: Activity },
  { key: "models", label: "模型接入", description: "Hermes 模型与提供商", icon: Bot },
  { key: "browsers", label: "浏览器管理", description: "运行时与浏览器资源", icon: Globe },
  { key: "processes", label: "进程管理", description: "重启、停止与退出", icon: RotateCcw },
  { key: "storage", label: "数据清理", description: "缓存、账号与素材", icon: Database },
  { key: "safety", label: "应急工具", description: "自检、导出与强制停止", icon: AlertTriangle },
]

const platformBrowserRows: Array<{
  key: PlatformBrowserKey
  label: string
  description: string
}> = [
  { key: "douyin", label: "抖音", description: "创作中心、登录校验和发布链路" },
  { key: "kuaishou", label: "快手", description: "账号登录、Cookie 复用和上传链路" },
  { key: "xiaohongshu", label: "小红书", description: "创作者中心与内容发布流程" },
  { key: "channels", label: "视频号", description: "Channels / Tencent 统一浏览器配置" },
  { key: "bilibili", label: "B 站", description: "创作中心与稿件发布流程" },
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

function SectionSwitcher({
  activeSection,
  onSelect,
}: {
  activeSection: SectionKey
  onSelect: (section: SectionKey) => void
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black p-2">
      <div className="flex flex-wrap gap-1.5">
        {sectionMeta.map((section) => {
          const Icon = section.icon
          const isActive = activeSection === section.key
          return (
            <button
              key={section.key}
              type="button"
              onClick={() => onSelect(section.key)}
              className={[
                "min-w-[118px] flex-1 rounded-xl border px-3 py-2.5 text-left transition-colors",
                isActive
                  ? "border-white/30 bg-white/10"
                  : "border-white/10 bg-black hover:bg-white/5",
              ].join(" ")}
            >
              <div className="flex items-start gap-2.5">
                <div
                  className={[
                    "mt-0.5 rounded-lg p-1.5",
                    isActive ? "bg-white/10 text-white" : "bg-black text-white/70",
                  ].join(" ")}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0">
                  <div className={isActive ? "text-sm font-medium text-white" : "text-sm font-medium text-white/90"}>
                    {section.label}
                  </div>
                  <div className="mt-1 text-[11px] leading-4 text-white/55">{section.description}</div>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black p-4">
      <div className="text-sm text-white/50">{label}</div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
      {hint ? <div className="mt-2 text-xs text-white/45">{hint}</div> : null}
    </div>
  )
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
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
    uninstallPatchright,
    uninstallPlaywright,
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

  const [activeSection, setActiveSection] = useState<SectionKey>("overview")
  const [confirmModal, setConfirmModal] = useState<ConfirmState>({
    open: false,
    title: "",
    description: "",
    onConfirm: () => {},
  })

  const handleConfirm = async () => {
    try {
      await confirmModal.onConfirm()
      setConfirmModal((prev) => ({ ...prev, open: false }))
    } catch (error: unknown) {
      toast({
        title: "操作失败",
        description: getErrorMessage(error) || "请求失败",
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

  const getEffectivePlatformBrowser = (
    platform: PlatformBrowserKey
  ): Exclude<PlatformBrowserChoice, "auto"> => {
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
    ? "网页模式"
    : appInfo == null
      ? "读取中"
      : appInfo.isPackaged
        ? "正式版"
        : "开发版"

  const openConfirm = (config: Omit<ConfirmState, "open">) => {
    setConfirmModal({
      open: true,
      ...config,
    })
  }

  const renderOverview = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <StatCard label="版本" value={appInfo?.version || "-"} />
        <StatCard label="模式" value={runtimeModeLabel} />
        <StatCard
          label="默认自动化运行时"
          value={currentRuntime === "playwright" ? "Playwright" : "Patchright"}
          hint={browserRuntimeInfo?.activeRuntime ? `当前生效: ${browserRuntimeInfo.activeRuntime}` : "当前未就绪"}
        />
      </div>

      <Card className="border-white/10 bg-black">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Activity className="h-5 w-5 text-white/70" />
            运行状态
          </CardTitle>
          <CardDescription className="text-white/60">
            服务健康、浏览器缓存目录和桌面退出行为一并放到这里。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-black p-4">
              <div className="text-sm text-white/50">浏览器缓存目录</div>
              <div className="mt-2 break-all font-mono text-xs text-white/80">
                {browserRuntimeInfo?.browsersPath || appInfo?.playwrightBrowserPath || "-"}
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black p-4">
              <div className="text-sm text-white/50">退出行为</div>
              <div className="mt-2 text-sm font-medium text-white">退出应用时停止所有受管进程</div>
              <div className="mt-2 text-xs text-white/50">适用于托盘退出与强制关闭前的统一预期。</div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {serviceEntries.length > 0 ? (
              serviceEntries.map(([key, value]) => (
                <div key={key} className="rounded-xl border border-white/10 bg-black p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-white">{statusLabels[key] || key}</div>
                    <Badge
                      variant="outline"
                      className={
                        value?.running
                          ? "border-white/30 bg-white/10 text-white"
                          : "border-white/15 bg-black text-white/60"
                      }
                    >
                      {value?.running ? "运行中" : "已停止"}
                    </Badge>
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-white/60">
                    <div>PID: {value?.pid ?? "-"}</div>
                    <div>外部进程: {value?.external ? "是" : "否"}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-white/10 bg-black/20 p-4 text-sm text-white/60 md:col-span-2 xl:col-span-3">
                当前还没有读取到运行状态。
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => window.open("/api/v1/system/logs", "_blank")}
              variant="secondary"
              className="border-white/10 bg-black text-white hover:bg-white/5"
            >
              <FileText className="mr-2 h-4 w-4" />
              查看日志
            </Button>
            <Button
              onClick={() =>
                openConfirm({
                  title: "退出应用",
                  description: "这会关闭桌面应用、移除托盘图标，并停止当前所有受管进程。",
                  onConfirm: quitApp,
                  variant: "danger",
                })
              }
              disabled={loading.quitApp}
              variant="secondary"
              className="border-white/10 bg-black text-white hover:bg-white/5"
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
    </div>
  )

  const renderModels = () => (
    <div className="space-y-6">
      <HermesProviderCard />
      <AIServiceProviderCard
        serviceType="cover_generation"
        title="图片生成"
        description="管理封面图、配图和图像生成模型提供商。"
        defaultOpen={false}
        providerOptions={[
          { value: "siliconflow", label: "SiliconFlow" },
          { value: "volcengine", label: "Volcengine" },
          { value: "openai_compatible", label: "OpenAI Compatible" },
          { value: "openai", label: "OpenAI" },
        ]}
        note="这里写入 cover_generation 服务配置，保持与现有封面生成链路一致。"
      />
      <AIServiceProviderCard
        serviceType="video_generation"
        title="视频生成"
        description="管理文生视频和视频生成模型提供商。"
        defaultOpen={false}
        providerOptions={[
          { value: "runwayml", label: "Runway" },
          { value: "pika", label: "Pika" },
          { value: "siliconflow", label: "SiliconFlow" },
          { value: "openai_compatible", label: "OpenAI Compatible" },
        ]}
        note="这里写入 video_generation 服务配置；测试连接会按后端现有视频生成探活逻辑执行。"
      />
      <AIServiceProviderCard
        serviceType="speech_recognition"
        title="语音接入"
        description="当前接入的是语音识别 / 转写模型，不伪装成并不存在的 TTS 配置。"
        defaultOpen={false}
        providerOptions={[
          { value: "openai", label: "OpenAI" },
          { value: "siliconflow", label: "SiliconFlow" },
          { value: "volcengine", label: "Volcengine" },
          { value: "openai_compatible", label: "OpenAI Compatible" },
        ]}
        note="这里写入 speech_recognition 服务配置，供语音识别和转写链路直接复用。"
      />
    </div>
  )

  const renderBrowsers = () => (
    <div className="space-y-6">
      <Card className="border-white/10 bg-black">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Globe className="h-5 w-5 text-white/70" />
            运行时与环境
          </CardTitle>
          <CardDescription className="text-white/60">
            这里处理默认自动化运行时、Python 环境和浏览器缓存目录。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-xl border border-white/10 bg-black p-4">
            <div className="text-sm text-white/50">当前 Python 环境</div>
            <div className="mt-2 break-all font-mono text-xs text-white/80">
              {browserRuntimeInfo?.pythonPath || "检测中..."}
            </div>
            <div className="mt-4 text-sm text-white/50">浏览器缓存目录</div>
            <div className="mt-2 break-all font-mono text-xs text-white/80">
              {browserRuntimeInfo?.browsersPath || appInfo?.playwrightBrowserPath || "检测中..."}
            </div>
            {!isElectronApp ? (
              <div className="mt-4 text-xs text-white/60">
                当前为网页模式：可查看并安装组件，但默认运行时切换仅桌面版可用。
              </div>
            ) : null}
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-black p-4">
            <div className="min-w-0">
              <div className="font-medium text-white">Chromium 无头模式</div>
              <div className="mt-1 text-xs text-white/60">切换后会自动重启受管服务，使自动化行为保持一致。</div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              {loading.setBrowserHeadless ? <Loader2 className="h-4 w-4 animate-spin text-white/60" /> : null}
              <Switch
                checked={browserHeadless === true}
                disabled={loading.setBrowserHeadless || typeof browserHeadless !== "boolean"}
                onCheckedChange={(checked) => void setBrowserHeadless(checked)}
                aria-label="切换无头模式"
              />
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm text-white/50">默认自动化运行时</div>
                <div className="mt-1 text-xs text-white/60">
                  安装逻辑保留互斥策略：安装一个运行时时，会强制卸载另一个，避免冲突。
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant={currentRuntime === "patchright" ? "default" : "secondary"}
                  className={currentRuntime === "patchright" ? "border-white/20 bg-white/10 text-white" : "border-white/10 bg-black text-white hover:bg-white/5"}
                  disabled={loading.setAutomationRuntime || !isElectronApp}
                  onClick={() => void setAutomationRuntime("patchright")}
                >
                  {loading.setAutomationRuntime && currentRuntime === "patchright" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Patchright
                </Button>
                <Button
                  variant={currentRuntime === "playwright" ? "default" : "secondary"}
                  className={currentRuntime === "playwright" ? "border-white/20 bg-white/10 text-white" : "border-white/10 bg-black text-white hover:bg-white/5"}
                  disabled={loading.setAutomationRuntime || !isElectronApp}
                  onClick={() => void setAutomationRuntime("playwright")}
                >
                  {loading.setAutomationRuntime && currentRuntime === "playwright" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Playwright
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]">
        <Card className="border-white/10 bg-black">
          <CardHeader>
            <CardTitle className="text-white">平台浏览器偏好</CardTitle>
            <CardDescription className="text-white/60">
              为不同平台分开指定默认浏览器，新的登录与发布上下文会遵循这里的配置。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {platformBrowserRows.map((platform) => (
              <div key={platform.key} className="rounded-xl border border-white/10 bg-black p-4">
                <div className="text-sm font-medium text-white">{platform.label}</div>
                <div className="mt-1 text-xs text-white/55">{platform.description}</div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full border border-white/10 bg-black px-2 py-1 text-white/65">
                    已设置：{platformBrowserLabels[platformBrowserPreferences[platform.key]]}
                  </span>
                  <span className="rounded-full border border-white/20 bg-white/10 px-2 py-1 text-white">
                    当前生效：{platformBrowserLabels[getEffectivePlatformBrowser(platform.key)]}
                  </span>
                </div>
                <div className="mt-4">
                  <Select
                    value={platformBrowserPreferences[platform.key]}
                    onValueChange={(value) =>
                      void setPlatformBrowserPreference(platform.key, value as PlatformBrowserChoice)
                    }
                    disabled={loading.setPlatformBrowser || !isElectronApp}
                  >
                    <SelectTrigger className="h-10 rounded-lg border-white/10 bg-black">
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
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-white/10 bg-black">
            <CardHeader>
              <CardTitle className="text-white">自动化运行时</CardTitle>
              <CardDescription className="text-white/60">
                在 Patchright 和 Playwright 之间切换，使用现有的互斥安装策略。
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3">
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Patchright</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.runtimes?.patchright?.installed
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/15 bg-black text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.runtimes?.patchright?.installed
                      ? `已安装 ${browserRuntimeInfo?.runtimes?.patchright?.version || ""}`.trim()
                      : "未安装"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.activeRuntime === "patchright"
                    ? "当前已启用"
                    : browserRuntimeInfo?.runtimes?.patchright?.installed
                      ? "可切换为默认自动化运行时"
                      : browserRuntimeInfo?.runtimes?.patchright?.error || "推荐用于 Chromium 自动化"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installPatchright()}
                    disabled={loading.installPatchright}
                    variant="secondary"
                    className="flex-1 border-white/10 bg-black text-white hover:bg-white/5"
                  >
                    {loading.installPatchright ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        安装中...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.runtimes?.patchright?.installed ? "重装 Patchright" : "安装 Patchright"}
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => void uninstallPatchright()}
                    disabled={loading.uninstallPatchright || !browserRuntimeInfo?.runtimes?.patchright?.installed}
                    variant="secondary"
                    className="border border-white/10 bg-black text-white/70 hover:bg-white/5"
                  >
                    {loading.uninstallPatchright ? (
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

              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Playwright</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.runtimes?.playwright?.installed
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/15 bg-black text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.runtimes?.playwright?.installed
                      ? `已安装 ${browserRuntimeInfo?.runtimes?.playwright?.version || ""}`.trim()
                      : "未安装"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.activeRuntime === "playwright"
                    ? "当前已启用"
                    : browserRuntimeInfo?.runtimes?.playwright?.installed
                      ? "可切换为默认自动化运行时"
                      : "可作为兼容后备运行时"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installPlaywright()}
                    disabled={loading.installPlaywright}
                    variant="secondary"
                    className="flex-1 border-white/10 bg-black text-white hover:bg-white/5"
                  >
                    {loading.installPlaywright ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        安装中...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.runtimes?.playwright?.installed ? "重装 Playwright" : "安装 Playwright"}
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => void uninstallPlaywright()}
                    disabled={loading.uninstallPlaywright || !browserRuntimeInfo?.runtimes?.playwright?.installed}
                    variant="secondary"
                    className="border border-white/10 bg-black text-white/70 hover:bg-white/5"
                  >
                    {loading.uninstallPlaywright ? (
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
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-black">
            <CardHeader>
              <CardTitle className="text-white">浏览器资源</CardTitle>
              <CardDescription className="text-white/60">
                管理本地 Chromium / Firefox 资源包。
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3">
              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Chromium</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.browsers?.chromium?.installed
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/15 bg-black text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.browsers?.chromium?.installed ? "已安装" : "未安装"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.browsers?.chromium?.version
                    ? `当前版本: ${browserRuntimeInfo?.browsers?.chromium?.version}`
                    : "安装后会写入 browsers/chromium/hibbiki-* 目录。"}
                </div>
                <div className="mt-3 break-all font-mono text-xs text-white/70">
                  {browserRuntimeInfo?.browsers?.chromium?.path || "安装后会在这里显示实际可执行文件路径。"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installChromium()}
                    disabled={loading.installChromium}
                    variant="secondary"
                    className="flex-1 border-white/10 bg-black text-white hover:bg-white/5"
                  >
                    {loading.installChromium ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        安装中...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.browsers?.chromium?.installed ? "重装 Chromium" : "下载 Chromium"}
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => void uninstallChromium()}
                    disabled={loading.uninstallChromium || !browserRuntimeInfo?.browsers?.chromium?.installed}
                    variant="secondary"
                    className="border border-white/10 bg-black text-white/70 hover:bg-white/5"
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

              <div className="rounded-xl border border-white/10 bg-black p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">Firefox</div>
                  <Badge
                    variant="outline"
                    className={
                      browserRuntimeInfo?.browsers?.firefox?.installed
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/15 bg-black text-white/60"
                    }
                  >
                    {browserRuntimeInfo?.browsers?.firefox?.installed ? "已安装" : "未安装"}
                  </Badge>
                </div>
                <div className="mt-3 text-xs text-white/60">
                  {browserRuntimeInfo?.browsers?.firefox?.version
                    ? `当前版本: ${browserRuntimeInfo?.browsers?.firefox?.version}`
                    : "安装后会写入项目本地 browsers 目录。"}
                </div>
                <div className="mt-3 break-all font-mono text-xs text-white/70">
                  {browserRuntimeInfo?.browsers?.firefox?.path || "安装后会在这里显示实际可执行文件路径。"}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => void installFirefox()}
                    disabled={loading.installFirefox}
                    variant="secondary"
                    className="flex-1 border-white/10 bg-black text-white hover:bg-white/5"
                  >
                    {loading.installFirefox ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        安装中...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {browserRuntimeInfo?.browsers?.firefox?.installed ? "重装 Firefox" : "下载 Firefox"}
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
                    className="border border-white/10 bg-black text-white/70 hover:bg-white/5"
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
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )

  const renderProcesses = () => (
    <div className="space-y-6">
      <Card className="border-white/10 bg-black">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <RotateCcw className="h-5 w-5 text-white/70" />
            常用控制
          </CardTitle>
          <CardDescription className="text-white/60">
            桌面版的前端、后端、Worker 和调度器重启入口统一放在这里。
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Button
            onClick={() =>
              openConfirm({
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
              openConfirm({
                title: "重启后端",
                description: "用于恢复本地 API 与登录链路。",
                onConfirm: restartBackend,
              })
            }
            disabled={loading.restartBackend}
            variant="secondary"
            className="w-full border-white/10 bg-black text-white hover:bg-white/5"
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
              openConfirm({
                title: "重启前端",
                description: "重新加载内置前端服务，但不会关闭桌面壳。",
                onConfirm: restartFrontend,
              })
            }
            disabled={loading.restartFrontend}
            variant="secondary"
            className="w-full border-white/10 bg-black text-white hover:bg-white/5"
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
              openConfirm({
                title: "停止所有服务",
                description: "这会停止前端、后端、工作进程与调度器管理的受管服务。",
                onConfirm: stopAll,
                variant: "danger",
              })
            }
            disabled={loading.stopAll}
            variant="secondary"
            className="w-full border-white/10 bg-black text-white hover:bg-white/5"
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
        </CardContent>
      </Card>
    </div>
  )

  const renderStorage = () => (
    <div className="space-y-6">
      <Card className="border-white/10 bg-black/0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Database className="h-5 w-5 text-white/70" />
            清理项
          </CardTitle>
          <CardDescription className="text-white/60">
            所有删除操作统一通过确认弹窗执行，避免误触。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <ActionRow
            icon={HardDrive}
            label="清理素材"
            description="删除本地素材文件和对应记录。"
            onAction={() =>
              openConfirm({
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
            label="清理账号与 Cookie"
            description="删除本地登录状态，之后需要重新登录或重新绑定。"
            onAction={() =>
              openConfirm({
                title: "清理账号与 Cookie",
                description: "这会删除本地账号、Cookie 和登录令牌。",
                onConfirm: clearAccounts,
                variant: "danger",
              })
            }
            loading={loading.clearAccounts}
          />

          <ActionRow
            icon={Trash2}
            label="清理浏览器数据"
            description="删除内置浏览器缓存、历史记录和临时文件。"
            onAction={() =>
              openConfirm({
                title: "清理浏览器数据",
                description: "这会清空 Electron 浏览器缓存及相关临时文件。",
                onConfirm: clearBrowser,
                variant: "danger",
              })
            }
            loading={loading.clearBrowser}
          />

          <ActionRow
            icon={Database}
            label="清理全部缓存"
            description="清空应用缓存、临时目录和 API 缓存。"
            onAction={() =>
              openConfirm({
                title: "清理全部缓存",
                description: "这会清除应用缓存和临时文件，适合在异常状态后做一次冷启动。",
                onConfirm: clearCache,
                variant: "danger",
              })
            }
            loading={loading.clearCache}
          />

          <ActionRow
            icon={Video}
            label="清理视频数据"
            description="删除本地视频文件、分析结果与历史记录。"
            onAction={() =>
              openConfirm({
                title: "清理视频数据",
                description: "这会删除本地视频文件与分析产物，操作不可撤销。",
                onConfirm: clearVideoData,
                variant: "danger",
              })
            }
            loading={loading.clearVideoData}
          />
        </CardContent>
      </Card>
    </div>
  )

  const renderSafety = () => (
    <div className="space-y-6">
      <Card className="border-white/10 bg-black">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <AlertTriangle className="h-5 w-5 text-white/70" />
            诊断与恢复
          </CardTitle>
          <CardDescription className="text-white/60">
            自检、日志导出和强制停止保留原有行为，只是从长页里单独分出来。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={async () => {
                try {
                  await runSelfCheck()
                } catch (error: unknown) {
                  toast({
                    title: "自检失败",
                    description: getErrorMessage(error),
                    variant: "destructive",
                  })
                }
              }}
              disabled={loading.runSelfCheck}
              variant="secondary"
              className="border-white/10 bg-black text-white hover:bg-white/5"
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
              onClick={async () => {
                try {
                  await exportLogs()
                } catch (error: unknown) {
                  toast({
                    title: "导出失败",
                    description: getErrorMessage(error),
                    variant: "destructive",
                  })
                }
              }}
              disabled={loading.exportLogs}
              variant="secondary"
              className="border-white/10 bg-black text-white hover:bg-white/5"
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

            <Button
              onClick={() =>
                openConfirm({
                  title: "强制停止相关进程",
                  description: "这会立即终止本地运行时进程。输入 CONFIRM 继续。",
                  requireInput: true,
                  confirmText: "CONFIRM",
                  onConfirm: forceKillProcesses,
                  variant: "danger",
                })
              }
              disabled={loading.forceKill}
              variant="secondary"
              className="border-white/10 bg-black text-white hover:bg-white/5"
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
          </div>
        </CardContent>
      </Card>
    </div>
  )

  const renderActiveSection = () => {
    switch (activeSection) {
      case "models":
        return renderModels()
      case "browsers":
        return renderBrowsers()
      case "processes":
        return renderProcesses()
      case "storage":
        return renderStorage()
      case "safety":
        return renderSafety()
      case "overview":
      default:
        return renderOverview()
    }
  }

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <div className="mx-auto max-w-7xl">
        <SectionSwitcher activeSection={activeSection} onSelect={setActiveSection} />
      </div>

      <div className="mx-auto max-w-7xl space-y-6">
        <div className="min-w-0">{renderActiveSection()}</div>
      </div>

      <div className="pointer-events-none sticky bottom-5 z-20 mx-auto flex max-w-7xl justify-end">
        <Button
          onClick={() => void refreshStatus()}
          disabled={loading.refreshStatus}
          variant="secondary"
          className="pointer-events-auto border-white/10 bg-black text-white shadow-[0_0_0_1px_rgba(255,255,255,0.06)] hover:bg-white/5"
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
