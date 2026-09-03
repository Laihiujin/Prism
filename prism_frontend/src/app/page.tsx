"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Users,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { fetcher } from "@/lib/api"
import { quickActions as fallbackQuickActions } from "@/lib/mock-data"
import {
  accountsResponseSchema,
  publishMetaResponseSchema,
  dashboardSchema,
  tasksResponseSchema,
} from "@/lib/schemas"
import { formatBeijingDateTime } from "@/lib/time"
import { PublishOtpDialog } from "@/components/publish/publish-otp-dialog"
import { PageHeader } from "@/components/layout/page-scaffold"
import CountUp from "@/components/CountUp"
import { cn } from "@/lib/utils"

export default function DashboardPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [clockReady, setClockReady] = useState(false)
  const [beijingClock, setBeijingClock] = useState("—")
  const [taskStatusFilter, setTaskStatusFilter] = useState<"all" | "pending" | "running" | "success" | "error">("all")

  useEffect(() => {
    setClockReady(true)
    setBeijingClock(formatBeijingDateTime())
    const timer = setInterval(() => {
      setBeijingClock(formatBeijingDateTime())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const {
    data: publishMeta,
    isLoading: publishLoading,
    isFetching: publishFetching,
  } = useQuery({
    queryKey: ["publish-meta"],
    queryFn: () => fetcher("/api/publish", publishMetaResponseSchema),
  })

  const {
    data: dashboard,
    isLoading: dashboardLoading,
    isFetching: dashboardFetching,
  } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => fetcher("/api/dashboard", dashboardSchema),
    refetchInterval: 15000,
  })

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["accounts-lite"],
    queryFn: () => fetcher("/api/accounts?limit=1000", accountsResponseSchema),
    refetchInterval: 30000,
  })

  const {
    data: taskQueue,
    isLoading: tasksLoading,
    isFetching: tasksRefreshing,
  } = useQuery({
    queryKey: ["tasks-dashboard"],
    queryFn: () => fetcher("/api/tasks", tasksResponseSchema),
    refetchInterval: 15000,
  })

  const accountTotal = dashboard?.data?.accounts?.total ?? 0
  const accountSyncLabel = useMemo(
    () => (dashboard?.data?.timestamp ? formatBeijingDateTime(dashboard.data.timestamp) : null),
    [dashboard]
  )
  const materialsTotal = dashboard?.data?.materials?.total ?? 0
  const pendingMaterialsCount = dashboard?.data?.materials?.byStatus?.pending ?? 0
  const publishedMaterialsCount = Math.max(materialsTotal - pendingMaterialsCount, 0)
  const accountList: any[] = accounts?.data ?? []
  const quickActionData = publishMeta?.quickActions ?? fallbackQuickActions
  const recordedTasks = taskQueue?.data ?? dashboard?.data?.tasks ?? []
  const errorTaskCount =
    taskQueue?.summary?.error ?? recordedTasks.filter((task: any) => task.status === "error").length

  const searchTerm = useMemo(
    () => (searchParams.get("q") ?? "").trim().toLowerCase(),
    [searchParams]
  )
  const hasSearch = searchTerm.length > 0
  const matchesSearch = (value: unknown) => {
    if (!hasSearch) return true
    return String(value ?? "").toLowerCase().includes(searchTerm)
  }

  const filteredTasks = useMemo(
    () =>
        hasSearch || taskStatusFilter !== "all"
        ? recordedTasks.filter((task: any) =>
          (taskStatusFilter === "all" || task.status === taskStatusFilter) &&
            [
              task.title,
              task.platform,
              task.account,
              task.status,
              task.material,
              task.result,
            ].some(matchesSearch)
          )
        : recordedTasks,
    [recordedTasks, hasSearch, searchTerm, taskStatusFilter]
  )

  const filteredAlerts = useMemo(() => {
    const alerts: Array<{ id: string | number; title: string; action: string }> = recordedTasks
      .filter((task: any) => task.status === "error")
      .slice(0, 5)
      .map((task: any) => ({
        id: task.id,
        title: `${task.platform} · ${task.account}`,
        action: task.result || "发布失败，请查看任务详情",
      }))
    if (!hasSearch) return alerts
    return alerts.filter((alert) =>
      [alert.title, alert.action].some(matchesSearch)
    )
  }, [recordedTasks, hasSearch, searchTerm])

  const filteredAccounts = useMemo(
    () =>
      hasSearch
        ? accountList.filter((account: any) =>
            [account.name, account.status, account.platform].some(matchesSearch)
          )
        : accountList,
    [accountList, hasSearch, searchTerm]
  )

  const filteredQuickActions = useMemo(
    () =>
      hasSearch
        ? quickActionData.filter((action: any) =>
            [action.title, action.description, action.href].some(matchesSearch)
          )
        : quickActionData,
    [quickActionData, hasSearch, searchTerm]
  )

  const alertsToShow: any[] = filteredAlerts

  const statCards = useMemo(
    () => [
      {
        label: "账号总数",
        value: accountTotal ? `${accountTotal}` : "—",
        delta: accountSyncLabel ? `最新同步：${accountSyncLabel}` : "等待同步",
        icon: Users,
        href: "/account",
      },
      {
        label: "素材储备",
        value: pendingMaterialsCount ? `${pendingMaterialsCount}` : "0",
        delta: materialsTotal
          ? `待发布 ${pendingMaterialsCount} · 已发布 ${publishedMaterialsCount}`
          : "等待入库",
        icon: BarChart3,
        href: "/materials",
      },
      {
        label: "异常待处理",
        value: errorTaskCount ? `${errorTaskCount}` : "0",
        delta: errorTaskCount ? "请优先处理失败任务" : "全部正常运行",
        icon: AlertTriangle,
        href: "/tasks",
      },
      {
        label: "系统时间 (UTC+8)",
        value: clockReady ? (beijingClock.split(" ")[1] ?? beijingClock) : "—",
        delta: clockReady ? beijingClock : "—",
        icon: Activity,
      },
    ],
    [accountTotal, accountSyncLabel, materialsTotal, errorTaskCount, beijingClock, clockReady]
  )

  const isLoading = dashboardLoading || publishLoading || accountsLoading || tasksLoading
  const isRefreshing = dashboardFetching || publishFetching || tasksRefreshing
  const tasksFetching = tasksLoading || tasksRefreshing

  const handleNavigate = (href?: string) => {
    if (href) router.push(href)
  }

  return (
    <div className="mx-auto max-w-[1440px] space-y-5 px-4 py-4 md:px-6 md:py-5">
      <PageHeader
        eyebrow="PRISM / CONTROL CENTER"
        title="矩阵投放仪表盘"
        // description="快手、抖音、视频号、小红书统一监控"
        actions={
          isRefreshing && (
            <Badge className="rounded-2xl border-border bg-black text-xs text-primary">
              数据刷新中...
            </Badge>
          )
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon
          return (
            <Card
              key={stat.label}
              className="group card-glow hairline-top relative cursor-pointer overflow-hidden border-border/80 bg-card/70 backdrop-blur-sm transition hover:bg-card"
              onClick={() => handleNavigate(stat.href)}
            >
              <div className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-black blur-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
              <CardHeader className="flex-row items-start justify-between pb-3">
                <div className="space-y-2">
                  <CardDescription className="font-terminal text-[11px] uppercase tracking-[0.08em] text-muted-foreground">{stat.label}</CardDescription>
                  <CardTitle className="text-2xl text-foreground">
                  {/^-?\d+(\.\d+)?$/.test(stat.value) ? (
                    <CountUp to={Number(stat.value)} separator="," duration={1.2} className="tabular-nums" />
                  ) : (
                    stat.value
                  )}
                  </CardTitle>
                </div>
                <Icon className="mt-0.5 h-4 w-4 text-foreground/45" />
              </CardHeader>
              <CardFooter className="justify-between border-t border-border/50 pt-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  {stat.delta}
                </div>
              </CardFooter>
            </Card>
          )
        })}
      </section>

      <PublishOtpDialog />

      <section className="grid gap-6">
        <Card className="hairline-top overflow-hidden border-border/80 bg-card/70 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center justify-between border-b border-border/50">
            <div>
              <CardTitle className="text-lg">任务管理库</CardTitle>
              <CardDescription>自动化及手动触发任务状态</CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-terminal text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{recordedTasks.length} records</span>
              <Button variant="ghost" className="h-7 gap-2 px-2 text-xs text-foreground/70 hover:text-foreground" onClick={() => router.push("/tasks")}>
                查看全部 <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex items-center gap-1 border-b border-border/50 pb-3 pt-1">
              {[...["all", "pending", "running", "success", "error"] as const].map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => setTaskStatusFilter(status)}
                  className={cn(
                    "border border-transparent px-2.5 py-1 text-[10px] uppercase tracking-[0.08em] text-muted-foreground transition",
                    taskStatusFilter === status && "border-border bg-accent text-foreground"
                  )}
                >
                  {status === "all" ? "全部" : status === "pending" ? "待执行" : status === "running" ? "运行中" : status === "success" ? "成功" : "失败"}
                </button>
              ))}
            </div>
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="text-muted-foreground">任务名称</TableHead>
                  <TableHead className="text-muted-foreground">平台</TableHead>
                  <TableHead className="text-muted-foreground">账号</TableHead>
                  <TableHead className="text-muted-foreground">时间</TableHead>
                  <TableHead className="text-right text-muted-foreground">状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTasks.length === 0 && (
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                      {hasSearch ? "未匹配到相关任务" : "暂无任务，请前往发布中心创建"}
                    </TableCell>
                  </TableRow>
                )}
                {filteredTasks.slice(0, 5).map((task: any) => (
                  <TableRow key={task.id} className="border-border/50 text-xs transition-colors hover:bg-accent/40">
                    <TableCell className="font-medium text-foreground">{task.title}</TableCell>
                    <TableCell>
                      <Badge className="border-border/80 bg-accent/60 text-foreground/80">{task.platform}</Badge>
                    </TableCell>
                    <TableCell className="text-foreground/80">{task.account}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {task.scheduledAt
                        ? `定时 · ${task.scheduledAt}`
                        : formatBeijingDateTime(task.createdAt)}
                    </TableCell>
                    <TableCell className={cn(
                      "text-right font-terminal text-xs",
                      task.status === "success" && "text-emerald-400",
                      task.status === "error" && "text-red-400",
                      task.status !== "success" && task.status !== "error" && "text-foreground/55"
                    )}>
                      <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-current align-middle" />
                      {task.status === "scheduled" ? "待定时" : task.status === "success" ? "已完成" : task.status === "error" ? "失败" : "排队中"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {tasksFetching && (
              <p className="mt-3 text-right text-xs text-muted-foreground">刷新任务中...</p>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <Card className="hairline-top space-y-5 border-border/80 bg-card/70 backdrop-blur-sm">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-lg">快捷入口</CardTitle>
            <CardDescription>常用矩阵工作流入口</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading && (
              <div className="rounded-xl border border-border/60 bg-background/40 p-4 text-sm text-muted-foreground">
                正在载入推荐操作...
              </div>
            )}
            {filteredQuickActions.map((action: any, idx: number) => (
              <div
                key={action.id || idx}
                className="group rounded-xl border border-border/60 bg-background/40 p-[1px] transition-colors hover:border-primary/30"
              >
                <div className="rounded-xl bg-background/40 p-4 transition group-hover:bg-accent/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{action.title}</p>
                      <p className="text-xs text-muted-foreground">{action.description}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-lg border border-border/60 bg-accent/40 text-foreground/80 hover:bg-accent hover:text-foreground"
                      onClick={() => handleNavigate(action.href)}
                    >
                      进入
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            {!isLoading && filteredQuickActions.length === 0 && (
              <div className="rounded-xl border border-border/60 bg-background/40 p-4 text-sm text-muted-foreground">
                {hasSearch ? "未匹配到相关操作" : "暂无可用操作"}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="hairline-top space-y-4 border-border/80 bg-card/70 backdrop-blur-sm">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-lg">失败任务提醒</CardTitle>
            <CardDescription>仅展示最近失败的任务</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {alertsToShow.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {hasSearch ? "未匹配到相关异常" : "当前账号状态正常，无异常任务。"}
              </p>
            )}
            {alertsToShow.map((alert) => (
              <div
                key={alert.id}
                className="rounded-xl border border-border bg-black p-4 text-sm text-white"
              >
                <p className="font-semibold">{alert.title}</p>
                <p className="text-xs text-white">{alert.action}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="hairline-top space-y-4 border-border/80 bg-card/70 backdrop-blur-sm">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-lg">账号运行概况</CardTitle>
            <CardDescription>实时同步后端账号状态</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading && (
              <div className="rounded-xl border border-border/60 bg-background/40 p-4 text-sm text-muted-foreground">
                正在同步账号数据...
              </div>
            )}
            {filteredAccounts.slice(0, 4).map((account) => (
              <div
                key={account.id}
                className="flex items-center justify-between rounded-xl border border-border/60 bg-background/40 p-4 transition-colors hover:border-primary/25"
              >
                <div>
                  <p className="text-sm font-semibold text-foreground">{account.name}</p>
                  <p className="text-xs text-muted-foreground">{account.boundAt}</p>
                </div>
                <Badge
                  className="border-none bg-accent/60 text-xs text-foreground/80"
                  variant={account.status === "正常" ? "secondary" : "destructive"}
                >
                  {account.status}
                </Badge>
              </div>
            ))}
            {!isLoading && filteredAccounts.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {hasSearch ? "未匹配到相关账号" : "暂无绑定账号，请先完成扫码绑定。"}
              </p>
            )}
          </CardContent>
          <CardFooter>
            <Button variant="link" className="gap-2 text-primary" onClick={() => router.push("/account")}>
              前往账号管理
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      </section>
    </div>
  )
}
