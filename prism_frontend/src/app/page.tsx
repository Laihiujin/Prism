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

export default function DashboardPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [clockReady, setClockReady] = useState(false)
  const [beijingClock, setBeijingClock] = useState("—")

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
      hasSearch
        ? recordedTasks.filter((task: any) =>
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
    [recordedTasks, hasSearch, searchTerm]
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
    <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="矩阵投放仪表盘"
        // description="快手、抖音、视频号、小红书统一监控"
        actions={
          isRefreshing && (
            <Badge className="rounded-2xl border-white/10 bg-white/10 text-xs text-white/80">
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
              className="group border-white/10 bg-black text-white cursor-pointer transition hover:bg-white/5"
              onClick={() => handleNavigate(stat.href)}
            >
              <CardHeader className="pb-2">
                <CardDescription className="text-white/60">{stat.label}</CardDescription>
                <CardTitle className="text-3xl text-white">{stat.value}</CardTitle>
              </CardHeader>
              <CardFooter className="justify-between text-sm text-white/60">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-white/70" />
                  {stat.delta}
                </div>
              </CardFooter>
            </Card>
          )
        })}
      </section>

      <PublishOtpDialog />

      <section className="grid gap-6">
        <Card className="border-white/10 bg-black text-white">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>任务管理库</CardTitle>
              <CardDescription>自动化及手动触发任务状态</CardDescription>
            </div>
            <Button variant="ghost" className="text-white/70 hover:text-white" onClick={() => router.push("/tasks")}>
              查看全部
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="border-white/10">
                  <TableHead className="text-white/60">任务名称</TableHead>
                  <TableHead className="text-white/60">平台</TableHead>
                  <TableHead className="text-white/60">账号</TableHead>
                  <TableHead className="text-white/60">时间</TableHead>
                  <TableHead className="text-right text-white/60">状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTasks.length === 0 && (
                  <TableRow className="border-white/10">
                    <TableCell colSpan={5} className="text-center text-sm text-white/60">
                      {hasSearch ? "未匹配到相关任务" : "暂无任务，请前往发布中心创建"}
                    </TableCell>
                  </TableRow>
                )}
                {filteredTasks.slice(0, 5).map((task: any) => (
                  <TableRow key={task.id} className="border-white/5">
                    <TableCell className="font-medium">{task.title}</TableCell>
                    <TableCell>
                      <Badge className="border-white/10 bg-white/10">{task.platform}</Badge>
                    </TableCell>
                    <TableCell>{task.account}</TableCell>
                    <TableCell>
                      {task.scheduledAt
                        ? `定时 · ${task.scheduledAt}`
                        : formatBeijingDateTime(task.createdAt)}
                    </TableCell>
                    <TableCell className="text-right text-sm text-white/70">
                      {task.status === "scheduled"
                        ? "待定时"
                        : task.status === "success"
                          ? "已完成"
                          : task.status === "error"
                            ? "失败"
                            : "排队中"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {tasksFetching && (
              <p className="mt-3 text-right text-xs text-white/60">刷新任务中...</p>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <Card className="space-y-5 border-white/10 bg-black text-white">
          <CardHeader className="pb-2">
            <CardTitle>快捷入口</CardTitle>
            <CardDescription>常用矩阵工作流入口</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading && (
              <div className="rounded-2xl border border-white/10 bg-black p-4 text-sm text-white/60">
                正在载入推荐操作...
              </div>
            )}
            {filteredQuickActions.map((action: any, idx: number) => (
              <div
                key={action.id || idx}
                className="group rounded-2xl border border-white/10 bg-black p-[1px]"
              >
                <div className="rounded-2xl bg-black/90 p-4 transition group-hover:bg-neutral-900/80">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold">{action.title}</p>
                      <p className="text-xs text-white/60">{action.description}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-xl bg-white/10 text-white"
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
              <div className="rounded-2xl border border-white/10 bg-black p-4 text-sm text-white/60">
                {hasSearch ? "未匹配到相关操作" : "暂无可用操作"}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="space-y-4 border-white/10 bg-black text-white">
          <CardHeader className="pb-2">
            <CardTitle>失败任务提醒</CardTitle>
            <CardDescription>仅展示最近失败的任务</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {alertsToShow.length === 0 && (
              <p className="text-sm text-white/60">
                {hasSearch ? "未匹配到相关异常" : "当前账号状态正常，无异常任务。"}
              </p>
            )}
            {alertsToShow.map((alert) => (
              <div
                key={alert.id}
                className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100"
              >
                <p className="font-semibold">{alert.title}</p>
                <p className="text-xs text-red-200">{alert.action}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="space-y-4 border-white/10 bg-black text-white">
          <CardHeader className="pb-2">
            <CardTitle>账号运行概况</CardTitle>
            <CardDescription>实时同步后端账号状态</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading && (
              <div className="rounded-2xl border border-white/10 bg-black p-4 text-sm text-white/60">
                正在同步账号数据...
              </div>
            )}
            {filteredAccounts.slice(0, 4).map((account) => (
              <div
                key={account.id}
                className="flex items-center justify-between rounded-2xl border border-white/10 bg-black p-4"
              >
                <div>
                  <p className="text-sm font-semibold">{account.name}</p>
                  <p className="text-xs text-white/60">{account.boundAt}</p>
                </div>
                <Badge
                  className="border-none bg-white/20 text-xs"
                  variant={account.status === "正常" ? "secondary" : "destructive"}
                >
                  {account.status}
                </Badge>
              </div>
            ))}
            {!isLoading && filteredAccounts.length === 0 && (
              <p className="text-sm text-white/60">
                {hasSearch ? "未匹配到相关账号" : "暂无绑定账号，请先完成扫码绑定。"}
              </p>
            )}
          </CardContent>
          <CardFooter>
            <Button variant="link" className="gap-2 text-white" onClick={() => router.push("/account")}>
              前往账号管理
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      </section>
    </div>
  )
}
