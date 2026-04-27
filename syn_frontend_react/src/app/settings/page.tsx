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
  frontend: "Frontend",
  backend: "Backend",
  supervisor: "Supervisor",
  playwright_worker: "Playwright Worker",
  celery_worker: "Celery Worker",
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
        title: "Action failed",
        description: error.message || "Request failed",
        variant: "destructive",
      })
    }
  }

  const serviceEntries = Object.entries(status ?? {}).filter(([, value]) => value)

  return (
    <div className="space-y-6 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="System Settings"
        description="Manage the desktop runtime, service processes, and local data"
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
                Refreshing
              </>
            ) : (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh status
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
              Runtime Overview
            </CardTitle>
            <CardDescription className="text-white/60">
              Inspect the packaged runtime, browser path, and service health.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">Version</div>
                <div className="mt-2 text-lg font-semibold text-white">{appInfo?.version || "-"}</div>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">Mode</div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {appInfo?.isPackaged ? "Packaged" : "Development"}
                </div>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/30 p-4">
                <div className="text-sm text-white/50">Tray Exit</div>
                <div className="mt-2 text-lg font-semibold text-white">Stops all managed processes</div>
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/50">Playwright Browser Path</div>
              <div className="mt-2 break-all font-mono text-xs text-white/80">
                {appInfo?.playwrightBrowserPath || "-"}
              </div>
            </div>

            <div className="flex items-center justify-between gap-4 rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="min-w-0">
                <div className="font-medium text-white">Headless browser</div>
                <div className="mt-1 text-sm text-white/60">
                  Turn this off to show automation browser windows. Creator centers still open in the built-in browser tabs.
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {loading.setBrowserHeadless && <Loader2 className="h-4 w-4 animate-spin text-white/60" />}
                <Switch
                  checked={appInfo?.runtimeSettings?.browserHeadless ?? true}
                  disabled={loading.setBrowserHeadless}
                  onCheckedChange={(checked) => void setBrowserHeadless(checked)}
                  aria-label="Toggle headless browser mode"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {serviceEntries.length > 0 ? (
                serviceEntries.map(([key, value]) => (
                  <div
                    key={key}
                    className="rounded-lg border border-white/10 bg-black/30 p-4"
                  >
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
                        {value?.running ? "Running" : "Stopped"}
                      </Badge>
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-white/60">
                      <div>PID: {value?.pid ?? "-"}</div>
                      <div>External: {value?.external ? "Yes" : "No"}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-white/10 bg-black/20 p-4 text-sm text-white/60">
                  No runtime status is available yet.
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
                View logs
              </Button>
              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Quit application",
                    description:
                      "This will close the desktop app, remove the tray icon, and stop all managed local processes.",
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
                    Quitting
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    Quit and stop all processes
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
              Process Control
            </CardTitle>
            <CardDescription className="text-white/60">
              Common service restart and stop actions for the desktop runtime.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Restart all services",
                    description:
                      "This restarts the frontend, backend, and workers. In packaged mode it uses supervisor for the managed restart path.",
                    onConfirm: restartAll,
                  })
                }
                disabled={loading.restartAll}
                className="w-full"
              >
                {loading.restartAll ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Restarting
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Restart all services
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Restart backend",
                    description:
                      "Use this to recover the local API and login pipeline. In packaged mode it calls supervisor's backend restart endpoint.",
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
                    Restarting
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Restart backend
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Restart frontend",
                    description: "This reloads the embedded app server without closing the desktop shell.",
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
                    Restarting
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Restart frontend
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Stop all services",
                    description:
                      "This stops the frontend, backend, workers, and supervisor-managed services. The desktop shell stays available in the tray.",
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
                    Stopping
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    Stop all services
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
              Data Cleanup
            </CardTitle>
            <CardDescription className="text-white/60">
              Remove local cache, login data, and generated business data.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <ActionRow
              icon={HardDrive}
              label="Clear materials"
              description="Remove local material files and records"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "Clear materials",
                  description: "This removes local material files and their records. The action cannot be undone.",
                  onConfirm: clearMaterials,
                  variant: "danger",
                })
              }
              loading={loading.clearMaterials}
            />

            <ActionRow
              icon={Cookie}
              label="Clear accounts and cookies"
              description="Remove local login state and require a new bind or sign-in"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "Clear accounts and cookies",
                  description: "This removes local account data, cookies, and login tokens.",
                  onConfirm: clearAccounts,
                  variant: "danger",
                })
              }
              loading={loading.clearAccounts}
            />

            <ActionRow
              icon={Trash2}
              label="Clear browser data"
              description="Remove embedded browser cache, history, and temporary files"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "Clear browser data",
                  description: "This clears the Electron browser cache and related temporary files.",
                  onConfirm: clearBrowser,
                  variant: "danger",
                })
              }
              loading={loading.clearBrowser}
            />

            <ActionRow
              icon={Database}
              label="Clear all cache"
              description="Empty app cache, temporary folders, and API cache"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "Clear all cache",
                  description: "This clears app cache and temporary files for a clean restart path.",
                  onConfirm: clearCache,
                  variant: "danger",
                })
              }
              loading={loading.clearCache}
            />

            <ActionRow
              icon={Video}
              label="Clear video data"
              description="Remove local videos, analysis data, and history"
              onAction={() =>
                setConfirmModal({
                  open: true,
                  title: "Clear video data",
                  description: "This removes local video files and analysis results. The action cannot be undone.",
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
              Emergency Tools
            </CardTitle>
            <CardDescription className="text-white/60">
              Use these when the desktop runtime is unstable and you need diagnostics fast.
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
                      title: "Self-check failed",
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
                    Running check
                  </>
                ) : (
                  <>
                    <Activity className="mr-2 h-4 w-4" />
                    Run self-check
                  </>
                )}
              </Button>

              <Button
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    title: "Force stop related processes",
                    description: "This immediately terminates local runtime processes. Type CONFIRM to continue.",
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
                    Stopping
                  </>
                ) : (
                  <>
                    <Power className="mr-2 h-4 w-4" />
                    Force stop processes
                  </>
                )}
              </Button>

              <Button
                onClick={async () => {
                  try {
                    await exportLogs()
                  } catch (error: any) {
                    toast({
                      title: "Export failed",
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
                    Exporting
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Export logs
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
