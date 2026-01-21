"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { Loader2, RotateCcw, Power, FileText, Trash2, Cookie, HardDrive, Database, AlertTriangle, Activity, Download, Video } from "lucide-react"
import { ConfirmModal } from "./components/ConfirmModal"
import { ActionRow } from "./components/ActionRow"
import { useSettingsActions } from "./hooks/useSettingsActions"

export default function SettingsPage() {
  const { toast } = useToast()
  const {
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
    loading
  } = useSettingsActions()

  const [confirmModal, setConfirmModal] = useState<{
    open: boolean
    title: string
    description: string
    confirmText?: string
    requireInput?: boolean
    onConfirm: () => void
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
      setConfirmModal({ ...confirmModal, open: false })
    } catch (error: any) {
      toast({
        title: "操作失败",
        description: error.message || "执行操作时出现错误",
        variant: "destructive"
      })
    }
  }

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="系统设置"
      />

      <div className="max-w-4xl mx-auto space-y-6">
        {/* Section 1: Process Control */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" />
              进程控制
            </CardTitle>
            <CardDescription className="text-white/60">
              管理核心服务进程
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Button Grid - 2 columns */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Button
                onClick={() => setConfirmModal({
                  open: true,
                  title: "重启所有服务",
                  description: "这将重启前端和后端服务，可能需要 10-30 秒时间。确定继续吗?",
                  onConfirm: restartAll,
                })}
                disabled={loading.restartAll}
                className="w-full"
              >
                {loading.restartAll ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    重启中...
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    重启所有服务
                  </>
                )}
              </Button>

              <Button
                onClick={() => setConfirmModal({
                  open: true,
                  title: "重启后端服务",
                  description: "这将重启 Python 后端服务 (FastAPI)，可能需要 5-10 秒时间。",
                  onConfirm: restartBackend,
                })}
                disabled={loading.restartBackend}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.restartBackend ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    重启中...
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    重启后端
                  </>
                )}
              </Button>

              <Button
                onClick={() => setConfirmModal({
                  open: true,
                  title: "重启前端服务",
                  description: "这将重启 Next.js 前端服务，可能需要 5-10 秒时间。",
                  onConfirm: restartFrontend,
                })}
                disabled={loading.restartFrontend}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.restartFrontend ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    重启中...
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    重启前端
                  </>
                )}
              </Button>

              <Button
                onClick={() => setConfirmModal({
                  open: true,
                  title: "停止所有服务",
                  description: "这将停止前端和后端服务。停止后需要手动重启应用程序。",
                  onConfirm: stopAll,
                  variant: "danger"
                })}
                disabled={loading.stopAll}
                variant="secondary"
                className="w-full bg-white/10"
              >
                {loading.stopAll ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    停止中...
                  </>
                ) : (
                  <>
                    <Power className="w-4 h-4 mr-2" />
                    停止所有服务
                  </>
                )}
              </Button>
            </div>

            <div className="pt-2">
              <Button
                onClick={() => window.open('/api/v1/system/logs', '_blank')}
                variant="link"
                className="text-primary hover:text-primary/80 p-0 h-auto"
              >
                <FileText className="w-4 h-4 mr-2" />
                查看日志
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Section 2: Data Cleanup */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              数据清理
            </CardTitle>
            <CardDescription className="text-white/60">
              清除本地数据和缓存
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <ActionRow
                icon={HardDrive}
                label="清除素材数据"
                description="删除所有本地素材文件和记录"
                onAction={() => setConfirmModal({
                  open: true,
                  title: "清除素材数据",
                  description: "这将删除所有本地素材文件和数据库记录。此操作不可逆!",
                  onConfirm: clearMaterials,
                  variant: "danger"
                })}
                loading={loading.clearMaterials}
              />

              <ActionRow
                icon={Cookie}
                label="清除账号与 Cookies"
                description="删除所有账号信息和登录凭证"
                onAction={() => setConfirmModal({
                  open: true,
                  title: "清除账号与 Cookies",
                  description: "这将删除所有账号信息、Cookies 和登录状态。需要重新登录所有账号。",
                  onConfirm: clearAccounts,
                  variant: "danger"
                })}
                loading={loading.clearAccounts}
              />

              <ActionRow
                icon={Trash2}
                label="清除浏览器数据"
                description="删除浏览器缓存、历史记录等"
                onAction={() => setConfirmModal({
                  open: true,
                  title: "清除浏览器数据",
                  description: "这将清除 Electron 浏览器的所有缓存、历史记录和临时数据。",
                  onConfirm: clearBrowser,
                  variant: "danger"
                })}
                loading={loading.clearBrowser}
              />

              <ActionRow
                icon={Database}
                label="清除所有缓存"
                description="清空所有应用缓存数据"
                onAction={() => setConfirmModal({
                  open: true,
                  title: "清除所有缓存",
                  description: "这将清除应用程序的所有缓存数据，包括 API 缓存、临时文件等。",
                  onConfirm: clearCache,
                  variant: "danger"
                })}
                loading={loading.clearCache}
              />

              <ActionRow
                icon={Video}
                label="清除视频数据"
                description="删除所有视频文件和分析数据"
                onAction={() => setConfirmModal({
                  open: true,
                  title: "清除视频数据",
                  description: "这将删除所有视频文件、视频分析数据和历史记录。此操作不可逆!",
                  onConfirm: clearVideoData,
                  variant: "danger"
                })}
                loading={loading.clearVideoData}
              />
            </div>
          </CardContent>
        </Card>

        {/* Section 3: Emergency */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              紧急操作
            </CardTitle>
            <CardDescription className="text-white/60">
              系统不稳定时使用
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
                      variant: "destructive"
                    })
                  }
                }}
                disabled={loading.runSelfCheck}
                variant="secondary"
                className="bg-white/10"
              >
                {loading.runSelfCheck ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    检查中...
                  </>
                ) : (
                  <>
                    <Activity className="w-4 h-4 mr-2" />
                    运行自检
                  </>
                )}
              </Button>

              <Button
                onClick={() => setConfirmModal({
                  open: true,
                  title: "强制终止进程",
                  description: "这将强制终止所有相关进程。这是危险操作，可能导致数据丢失。请输入 CONFIRM 确认。",
                  requireInput: true,
                  confirmText: "CONFIRM",
                  onConfirm: forceKillProcesses,
                  variant: "danger"
                })}
                disabled={loading.forceKill}
                variant="destructive"
              >
                {loading.forceKill ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    终止中...
                  </>
                ) : (
                  <>
                    <Power className="w-4 h-4 mr-2" />
                    强制终止进程
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
                      variant: "destructive"
                    })
                  }
                }}
                disabled={loading.exportLogs}
                variant="secondary"
                className="bg-white/10"
              >
                {loading.exportLogs ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    导出中...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    导出日志
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Confirm Modal */}
      <ConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        description={confirmModal.description}
        confirmText={confirmModal.confirmText}
        requireInput={confirmModal.requireInput}
        variant={confirmModal.variant}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmModal({ ...confirmModal, open: false })}
      />
    </div>
  )
}
