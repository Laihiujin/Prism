"use client"

import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import {
  Activity,
  AlertTriangle,
  Cookie,
  Database,
  Download,
  FileText,
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
import { useSettingsActions } from "./hooks/useSettingsActions"

const statusLabels: Record<string, string> = {
  frontend: "前端",
  backend: "后端",
  supervisor: "调度器",
  playwright_worker: "Playwright 工作者",
  celery_worker: "Celery 工作者",
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
    quitApp,
    clearMaterials,
    clearAccounts,
    clearBrowser,
    clearCache,
    clearVideoData,
    runSelfCheck,
    forceKillProcesses,
    exportLogs,
    loading,
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
                <div className="mt-2 text-lg font-semibold text-white">
                  {appInfo?.isPackaged ? "打包版" : "开发版"}
                </div>
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
                <div className="font-medium text-white">无头浏览器</div>
                <div className="mt-1 text-sm text-white/60">
                  关闭后会显示自动化浏览器窗口。创作者中心仍会在内置浏览器标签页中打开。
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {loading.setBrowserHeadless && <Loader2 className="h-4 w-4 animate-spin text-white/60" />}
                <Switch
                  checked={appInfo?.runtimeSettings?.browserHeadless ?? true}
                  disabled={loading.setBrowserHeadless}
                  onCheckedChange={(checked) => void setBrowserHeadless(checked)}
                  aria-label="切换无头浏览器模式"
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
