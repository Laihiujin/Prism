"use client"

import { Suspense, startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react"
import NextImage from "next/image"
import { useSearchParams } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ExternalLink, Loader2, Plus, QrCode, RefreshCcw } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/use-toast"
import { DataTable } from "@/components/ui/data-table"
import { fetcher } from "@/lib/api"
import { backendBaseUrl } from "@/lib/env"
import { type Account, type PlatformKey } from "@/lib/mock-data"
import { accountsResponseSchema } from "@/lib/schemas"
import { type ColumnDef } from "@tanstack/react-table"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PageHeader, PageSection } from "@/components/layout/page-scaffold"

const platformTabs: { label: string; value: PlatformKey }[] = [
  { label: "全部", value: "all" },
  { label: "快手", value: "kuaishou" },
  { label: "抖音", value: "douyin" },
  { label: "视频号", value: "channels" },
  { label: "小红书", value: "xiaohongshu" },
  { label: "B站", value: "bilibili" },
]

const platformLabelMap: Record<PlatformKey, string> = {
  all: "全部",
  kuaishou: "快手",
  douyin: "抖音",
  channels: "视频号",
  xiaohongshu: "小红书",
  bilibili: "B站",
}

export default function AccountPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-2xl border border-white/10 bg-black p-6 text-sm text-white/60">加载账户页...</div>
      }
    >
      <AccountPageContent />
    </Suspense>
  )
}

const platformTypeMap: Record<PlatformKey, string> = {
  all: "3",
  kuaishou: "4",
  douyin: "3",
  channels: "2",
  xiaohongshu: "1",
  bilibili: "5",
}

const statusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  正常: { label: "正常", variant: "secondary" },
  valid: { label: "正常", variant: "secondary" },
  异常: { label: "异常", variant: "destructive" },
  expired: { label: "失效", variant: "destructive" },
  error: { label: "错误", variant: "destructive" },
  待激活: { label: "待激活", variant: "default" },
  pending: { label: "待激活", variant: "default" },
}

const loginStatusMap: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  logged_in: { label: "在线", variant: "secondary" },
  session_expired: { label: "掉线", variant: "destructive" },
  skipped: { label: "-", variant: "outline" },
  unknown: { label: "未检测", variant: "outline" },
}

interface AccountFormState {
  id?: string
  name: string
  platform: PlatformKey
}

function AccountPageContent() {
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const { data: accountResponse, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => fetcher("/api/accounts?limit=1000", accountsResponseSchema),
    refetchInterval: 10000,
  })

  useEffect(() => {
    console.log("API Response:", accountResponse)
    if (error) console.error("API Error:", error)
  }, [accountResponse, error])

  const [accounts, setAccounts] = useState<Account[]>([])
  const [keyword, setKeyword] = useState("")
  const [activeTab, setActiveTab] = useState<PlatformKey>("all")
  const [isSyncing, setIsSyncing] = useState(false)
  const [isStatusChecking, setIsStatusChecking] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formState, setFormState] = useState<AccountFormState>({ name: "", platform: "kuaishou" })
  const [bindingStatus, setBindingStatus] = useState<"idle" | "pending" | "code" | "success" | "error">("idle")
  const [qrImage, setQrImage] = useState<string | null>(null)
  const { toast } = useToast()
  const keywordInputRef = useRef<HTMLInputElement | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeSessionRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    activeSessionRef.current = null
  }, [])

  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  useEffect(() => {
    if (!accountResponse?.data || !Array.isArray(accountResponse.data)) return
    startTransition(() => {
      setAccounts(accountResponse.data)
    })
  }, [accountResponse])

  useEffect(() => {
    if (!accounts.length) return
    const snapshot = {
      accounts: accounts.map((account) => ({
        account_id: account.id,
        platform: account.platform,
      })),
    }
    fetch("/api/accounts/sync-frontend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot),
    }).catch((error) => {
      console.warn("Sync frontend accounts failed:", error)
    })
  }, [accounts])

  useEffect(() => {
    const platformParam = searchParams.get("platform") as PlatformKey | null
    if (platformParam && platformTabs.some((tab) => tab.value === platformParam)) {
      setActiveTab(platformParam)
    }
    const q = searchParams.get("q")
    if (q) {
      setKeyword(q)
    }
    if (searchParams.get("focus") === "search") {
      keywordInputRef.current?.focus()
    }
  }, [searchParams])

  const filteredAccounts = useMemo(() => {
    return accounts.filter((account) => {
      const matchTab = activeTab === "all" || account.platform === activeTab
      const matchKeyword =
        !keyword ||
        account.name.toLowerCase().includes(keyword.toLowerCase()) ||
        account.id.toLowerCase().includes(keyword.toLowerCase())
      return matchTab && matchKeyword
    })
  }, [accounts, activeTab, keyword])

  const resetDialogState = () => {
    setFormState({ id: undefined, name: "", platform: "kuaishou" })
    setBindingStatus("idle")
    setQrImage(null)
  }

  const openEditDialog = (account: Account) => {
    setFormState({
      id: account.id,
      name: (account as any).note || account.name,
      platform: account.platform
    })
    setBindingStatus("success")
    setDialogOpen(true)
  }

  const startBinding = async () => {
    setBindingStatus("pending")
    setQrImage(null)

    const currentLoginId = formState.name || `account_${Date.now()}`

    try {
      // Step 1: 查询最佳登录方式
      const platformMap: Record<PlatformKey, string> = {
        all: "douyin",
        kuaishou: "kuaishou",
        douyin: "douyin",
        channels: "tencent",
        xiaohongshu: "xiaohongshu",
        bilibili: "bilibili",
      }

      const platform = platformMap[formState.platform]
      const unifiedUrl = `${backendBaseUrl}/api/v1/auth/login/unified?platform=${platform}&account_id=${encodeURIComponent(currentLoginId)}`

      const unifiedRes = await fetch(unifiedUrl)
      const unifiedData = await unifiedRes.json()

      await startApiLogin(currentLoginId)
    } catch (error) {
      console.error('Login initialization failed:', error)
      setBindingStatus("error")
      toast({
        variant: "destructive",
        title: "登录初始化失败",
        description: "二维码获取失败，请重试或联系管理员",
      })
    }
  }

  const startApiLogin = async (loginId: string) => {
    try {
      // Step 1: 生成二维码
      const platformMap: Record<PlatformKey, string> = {
        all: "douyin",
        kuaishou: "kuaishou",
        douyin: "douyin",
        channels: "tencent",
        xiaohongshu: "xiaohongshu",
        bilibili: "bilibili",
      }

      const platform = platformMap[formState.platform]
      const qrRes = await fetch(`/api/v1/auth/qrcode/generate?platform=${platform}&account_id=${encodeURIComponent(loginId)}`, {
        method: 'POST'
      })

      let qrData: any = null
      let rawText = ""
      try {
        rawText = await qrRes.text()
        qrData = rawText ? JSON.parse(rawText) : null
      } catch (err) {
        console.error("Failed to parse QR response", err, rawText)
      }

      if (!qrRes.ok || !qrData?.success) {
        const msg =
          qrData?.detail ||
          qrData?.error ||
          qrData?.message ||
          rawText ||
          `Status ${qrRes.status}`
        throw new Error(msg || 'Failed to generate QR code')
      }

      // Step 2: 显示二维码
      setQrImage(qrData.qr_image)
      setBindingStatus("code")

      // Step 3: Poll login status
      const sessionId = qrData.qr_id
      stopPolling()
      activeSessionRef.current = sessionId
      pollIntervalRef.current = setInterval(async () => {
        try {
          if (activeSessionRef.current !== sessionId) return
          const statusRes = await fetch(`/api/v1/auth/qrcode/poll?session_id=${sessionId}`)
          if (!statusRes.ok) {
            if (statusRes.status === 404) {
              stopPolling()
              return
            }
            throw new Error(`Status ${statusRes.status}`)
          }
          const statusData = await statusRes.json()

          if (statusData.status === 'confirmed') {
            stopPolling()
            setBindingStatus("success")
            toast({
              variant: "success",
              title: "Scan confirmed",
              description: "Account linked. Syncing data...",
            })

            // Refresh account list right away.
            await queryClient.invalidateQueries({ queryKey: ["accounts"] })
            await refetch()

            setTimeout(() => {
              setDialogOpen(false)
              setFormState({ id: "", name: "", platform: "kuaishou" })
              setBindingStatus("idle")
              toast({
                variant: "success",
                title: "Account added",
                description: "Account info is synced.",
              })
            }, 500)
          } else if (statusData.status === 'scanned') {
            toast({
              title: "Scanned",
              description: "Confirm login on your phone.",
            })
          } else if (statusData.status === 'expired') {
            stopPolling()
            setBindingStatus("error")
            toast({
              variant: "destructive",
              title: "QR expired",
              description: "Please get a new QR code.",
            })
          } else if (statusData.status === 'failed') {
            stopPolling()
            setBindingStatus("error")
            toast({
              variant: "destructive",
              title: "Login failed",
              description: statusData.message || "Please retry.",
            })
          }
        } catch (error) {
          console.error('Poll error:', error)
        }
      }, 2000) // Poll every 2 seconds.

      // 5 minute timeout
      pollTimeoutRef.current = setTimeout(() => {
        if (activeSessionRef.current !== sessionId) return
        stopPolling()
        setBindingStatus("error")
        toast({
          variant: "destructive",
          title: "Login timeout",
          description: "Please get a new QR code.",
        })
      }, 300000)

    } catch (error) {
      console.error('API login error:', error)
      setBindingStatus("error")
      toast({
        variant: "destructive",
        title: "登录失败",
        description: "请重试或联系管理员",
      })
    }
  }

  const handleSaveAccount = async () => {
    if (formState.id) {
      try {
        const payload = {
          id: formState.id,
          type: Number(platformTypeMap[formState.platform]),
          userName: formState.name,
        }
        const response = await fetch(`${backendBaseUrl}/api/v1/accounts/${formState.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: formState.name
          }),
        })
        if (!response.ok) throw new Error("update failed")
        toast({ variant: "success", title: "账号信息已更新", description: `${formState.name || '账号'} 已完成修改` })
        setDialogOpen(false)
        await refetch()
      } catch (error) {
        console.error(error)
        toast({ variant: "destructive", title: "更新失败", description: "请稍后再试" })
      }
      return
    }

    if (bindingStatus !== "success") {
      toast({
        title: "等待扫码完成",
        description: "请先点击“获取二维码”并在手机端确认登录",
      })
      return
    }

    const nickname = formState.name || "新账号"
    setDialogOpen(false)
    await refetch()
    toast({ variant: "success", title: "账号绑定成功", description: `${nickname} 已加入矩阵` })
  }

  const handleDelete = async (id: string) => {
    try {
      const response = await fetch(`${backendBaseUrl}/api/v1/accounts/${encodeURIComponent(id)}`, {
        method: "DELETE"
      })
      if (!response.ok) throw new Error("delete failed")
      toast({ title: "账号已删除", description: "该账号将不再参与自动化任务" })
      await refetch()
    } catch (error) {
      console.error(error)
      toast({ variant: "destructive", title: "删除失败", description: "请稍后再试" })
    }
  }

  const handleOpenCreatorCenter = async (account: Account) => {
    const accountId = account.id
    try {
      // 1. 获取需要打开的 URL 和 Cookie 数据
      const response = await fetch(
        `${backendBaseUrl}/api/v1/accounts/${encodeURIComponent(accountId)}/creator-center/data`,
        { method: "GET" }
      )
      const res = await response.json()

      if (!response.ok || !res.success) {
        throw new Error(res.detail || res.message || "获取账号数据失败")
      }

      const { url, storage_state, platform } = res.data
      const cookies = storage_state?.cookies || []

      // 2. 检测是否正在 Electron Shell 中运行
      const isElectron = typeof window !== 'undefined' &&
        (window.navigator.userAgent.indexOf('Electron') > -1 || (window as any).electronAPI);

      if (isElectron) {
        // 通知外部 Shell 打开新标签并注入 Cookie
        window.parent.postMessage({
          type: 'OPEN_CREATOR_TAB',
          url: url,
          cookies: cookies,
          platform: platform
        }, '*')

        toast({
          title: "正在侧边栏打开",
          description: `正在为您加载 ${account.platform} 创作中心...`,
        })
      } else {
        // 非 Electron 环境，回退到原有后台打开逻辑 (仅用于兼容性)
        const openResponse = await fetch(
          `${backendBaseUrl}/api/v1/accounts/${encodeURIComponent(accountId)}/creator-center/open`,
          { method: "POST" }
        )
        if (!openResponse.ok) throw new Error("启动浏览器失败")
        toast({
          title: "已请求打开创作者中心",
          // description: "浏览器窗口已启动 (非集成模式)",
        })
      }
    } catch (e) {
      console.error("Open Creator Center Error:", e)
      toast({ variant: "destructive", title: "打开失败", description: String(e) })
    }
  }

  // 检查单个账号登录状态
  const checkAccountLoginStatus = async (accountId: string) => {
    try {
      const response = await fetch(`/api/v1/creator/check-login-status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_ids: [accountId] })
      })

      if (!response.ok) {
        throw new Error("检查失败")
      }

      const result = await response.json()

      if (result.success) {
        // 强制刷新账号列表
        await queryClient.invalidateQueries({ queryKey: ["accounts"] })
        await refetch()

        const logged_in = result.logged_in || 0
        const session_expired = result.session_expired || 0
        const errors = result.errors || 0

        toast({
          title: "正常",
          // description: `在线=${logged_in}, 掉线=${session_expired}, 错误=${errors}`
        })
      }
    } catch (e) {
      console.error("Check Login Status Error:", e)
      toast({ variant: "destructive", title: "检查失败", description: String(e) })
    }
  }


  const columns: ColumnDef<Account>[] = [
    {
      accessorKey: "account",
      header: "账号",
      cell: ({ row }) => {
        const originalName = (row.original as any).original_name || row.original.name
        const displayName = originalName || row.original.name

        return (
          <div className="flex items-center gap-3">
            <img
              src={row.original.avatar || `https://api.dicebear.com/9.x/identicon/svg?seed=${encodeURIComponent(row.original.name)}`}
              alt={row.original.name}
              referrerPolicy="no-referrer"
              className="h-10 w-10 shrink-0 rounded-full border border-white/10 bg-black object-cover p-0.5"
            />
            <div className="flex flex-col">
              <TooltipProvider delayDuration={150}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="flex items-center gap-1 text-left font-medium text-sm hover:underline underline-offset-4"
                      onClick={() => handleOpenCreatorCenter(row.original)}
                    >
                      <span>{displayName}</span>
                      <ExternalLink className="h-3.5 w-3.5 text-white/50" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="border-white/10 bg-black text-white">
                    跳转创作中心
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        )
      },
    },
    {
      id: "platform_id",
      header: "平台 ID",
      cell: ({ row }) => {
        const userId = (row.original as any).user_id
        const accountId = row.original.id
        const displayAccountId = userId
        // const displayUid = accountId || userId

        const copyToClipboard = (text: string, label: string) => {
          navigator.clipboard.writeText(text).then(() => {
            toast({
              title: "已复制",
              description: `${label} 已复制到剪贴板`,
            })
          }).catch(() => {
            toast({
              variant: "destructive",
              title: "复制失败",
              description: "请手动复制",
            })
          })
        }

        return (
          <div className="flex flex-col items-start gap-1.5">
            <div
              className="flex items-center gap-1.5 cursor-pointer hover:bg-white/5 px-1.5 py-0.5 rounded transition-colors group"
              onClick={() => copyToClipboard(displayAccountId, "账号ID")}
              title="点击复制"
            >
              <span className="text-[10px] text-white/40">账号ID:</span>
              <Badge variant="outline" className="text-[10px] px-1 py-0 h-4 border-white/20 text-white/50 font-mono group-hover:border-primary/50 group-hover:text-primary/70 transition-colors">
                {displayAccountId}
              </Badge>
            </div>
            {/* {displayUid && (
              <div
                className="flex items-center gap-1.5 cursor-pointer hover:bg-white/5 px-1.5 py-0.5 rounded transition-colors group"
                onClick={() => copyToClipboard(displayUid, "UID")}
                title="点击复制"
              >
                <span className="text-[10px] text-white/40">UID:</span>
                <span className="text-xs text-white/70 font-mono group-hover:text-primary/70 transition-colors">{displayUid}</span>
              </div>
            )} */}
          </div>
        )
      }
    },
    {
      accessorKey: "platform",
      header: "平台",
      cell: ({ row }) => (
        <div className="flex justify-start">
          <Badge className="border-none bg-white/10 text-xs hover:bg-white/20">
            {platformLabelMap[row.original.platform] ?? row.original.platform}
          </Badge>
        </div>
      ),
    },
    {
      id: "login_status",
      header: "登录状态",
      cell: ({ row }) => {
        // B站特殊处理：无论 login_status 是什么，都默认显示为在线（因为使用biliup库）
        const platform = row.original.platform
        let loginStatus = (row.original as any).login_status || "unknown"

        if (platform === "bilibili") {
          // B站账号始终显示为在线
          loginStatus = "logged_in"
        }

        const loginConfig = loginStatusMap[loginStatus] || { label: loginStatus, variant: "outline" }
        const accountId = row.original.id

        // 所有状态都可点击重新检测
        return (
          <div className="flex justify-start">
            <button
              onClick={() => checkAccountLoginStatus(accountId)}
              className="group transition-all"
            >
              <Badge
                variant={loginConfig.variant as any}
                className="border-none text-xs cursor-pointer group-hover:ring-2 group-hover:ring-white/20 group-hover:scale-105 transition-all"
              >
                {loginConfig.label}
              </Badge>
            </button>
          </div>
        )
      },
    },
    {
      accessorKey: "boundAt",
      header: "绑定时间",
      cell: ({ row }) => {
        const dateStr = row.original.boundAt
        if (!dateStr) return <span className="text-sm text-white/40">-</span>
        try {
          const date = new Date(dateStr)
          const formatted = `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
          return <span className="text-sm text-white/70 font-mono">{formatted}</span>
        } catch (e) {
          return <span className="text-sm text-white/70">{dateStr}</span>
        }
      },
    },
    {
      accessorKey: "note",
      header: "备注",
      cell: ({ row }) => {
        const note = (row.original as any).note
        if (!note || note.startsWith("account_")) return <span className="text-white/30">-</span>
        return <span className="text-sm text-white/70">{note}</span>
      }
    },
    {
      id: "actions",
      header: () => <div className="text-right">操作</div>,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="secondary" className="h-8 rounded-xl px-3 text-xs" onClick={() => openEditDialog(row.original)}>
            编辑
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="destructive" className="h-8 rounded-xl px-3 text-xs">
                删除
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认删除账号？</AlertDialogTitle>
                <AlertDialogDescription>该账号将从矩阵中移除，无法参与后续自动化任务。</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={() => handleDelete(row.original.id)}>删除</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="账号管理"
        // description="集中管理矩阵账号，支持扫码绑定"
        actions={
          <>

            <Dialog
              open={dialogOpen}
              onOpenChange={(open) => {
                setDialogOpen(open)
                if (!open) {
                  setBindingStatus("idle")
                  setQrImage(null)
                }
              }}
            >
              <DialogTrigger asChild>
                <Button className="rounded-2xl">
                  <Plus className="h-4 w-4" />
                  添加账号
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{formState.id ? "编辑账号" : "扫码绑定账号"}</DialogTitle>
                  <DialogDescription>支持选择平台、昵称并通过扫码绑定</DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>平台</Label>
                    <Select
                      value={formState.platform}
                      onValueChange={(value: PlatformKey) => {
                        setBindingStatus("idle")
                        setQrImage(null)
                        setFormState((prev) => ({ ...prev, platform: value }))
                      }}
                      disabled={!!formState.id}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择平台" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="kuaishou">快手</SelectItem>
                        <SelectItem value="douyin">抖音</SelectItem>
                        <SelectItem value="channels">视频号</SelectItem>
                        <SelectItem value="xiaohongshu">小红书</SelectItem>
                        <SelectItem value="bilibili">B站</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>备注（可选）</Label>
                    <Input
                      placeholder="为账号添加备注"
                      value={formState.name}
                      onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
                    />
                  </div>
                  {!formState.id && (
                    <div className="rounded-2xl border border-white/10 bg-black p-4">
                      <p className="text-sm font-semibold">二维码登录</p>
                      <p className="text-xs text-white/60">点击按钮获取二维码</p>
                      <div className="mt-4 flex flex-col items-center justify-center gap-3 py-4">
                        {bindingStatus === "idle" && (
                          <Button variant="secondary" onClick={startBinding}>
                            <QrCode className="h-4 w-4" />
                            获取二维码
                          </Button>
                        )}
                        {bindingStatus === "pending" && (
                          <div className="flex flex-col items-center gap-2 text-sm text-white/70 w-full px-8">
                            <Loader2 className="h-6 w-6 animate-spin text-white" />
                            <span>正在初始化二维码...</span>
                            <Progress value={33} className="w-full h-1 mt-2" />
                          </div>
                        )}
                        {bindingStatus === "code" && qrImage && (
                          <div className="flex flex-col items-center gap-3">
                            <NextImage
                              src={qrImage}
                              alt="登录二维码"
                              width={200}
                              height={200}
                              className="h-40 w-40 rounded-2xl border border-white/10 bg-black p-3"
                            />
                            <p className="text-xs text-white/60">请使用 {platformLabelMap[formState.platform]} App 扫码</p>
                            <Button size="sm" variant="ghost" className="rounded-xl bg-white/10" onClick={startBinding}>
                              刷新二维码
                            </Button>
                          </div>
                        )}
                        {bindingStatus === "success" && (
                          <div className="flex flex-col items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                            <span>已完成扫码，可点击下一步完成绑定</span>
                          </div>
                        )}
                        {bindingStatus === "error" && (
                          <div className="flex flex-col items-center gap-2 rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                            <span>连接出错，请重新获取二维码</span>
                            <Button size="sm" variant="ghost" className="rounded-xl bg-white/10" onClick={startBinding}>
                              重新获取
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="ghost" className="rounded-2xl border border-white/10 bg-white/5" onClick={() => setDialogOpen(false)}>
                    取消
                  </Button>
                  <Button className="rounded-2xl" onClick={handleSaveAccount}>
                    {formState.id ? "保存修改" : bindingStatus === "success" ? "完成绑定" : "下一步"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        }
      />

      <PageSection
        title="账号列表"
        description={`当前已绑定 ${accounts.length} 个矩阵账号${isFetching ? " · 刷新中..." : ""}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="default"
              className="rounded-2xl"
              onClick={async () => {
                setIsStatusChecking(true)
                try {
                  // 高并发检测所有账号：收集所有账号ID，传给Worker一次性检查
                  const allAccountIds = accounts.map(acc => acc.id)
                  if (allAccountIds.length === 0) {
                    toast({ title: "无账号", description: "当前没有账号可检测" })
                    return
                  }

                  const res = await fetch(`/api/v1/creator/check-login-status`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ account_ids: allAccountIds })  // 传入所有账号ID
                  })
                  const json = await res.json()
                  if (json.success) {
                    // 强制刷新账号列表
                    await queryClient.invalidateQueries({ queryKey: ["accounts"] })
                    await refetch()

                    const logged_in = json.logged_in || 0
                    const session_expired = json.session_expired || 0
                    const errors = json.errors || 0

                    toast({
                      variant: "success",
                      title: "检测完成",
                      // description: `在线=${logged_in}, 掉线=${session_expired}, 错误=${errors}`
                    })
                  } else {
                    throw new Error(json.message || "检测失败")
                  }
                } catch (e) {
                  toast({ variant: "destructive", title: "检测失败", description: String(e) })
                } finally {
                  setIsStatusChecking(false)
                }
              }}
              disabled={isFetching || isStatusChecking}
            >
              {isStatusChecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              {isStatusChecking ? "检测中..." : "检测所有账号登录状态"}
            </Button>
            <Button
              variant="destructive"
              className="rounded-2xl"
              onClick={async () => {
                try {
                  const res = await fetch(`${backendBaseUrl}/api/v1/accounts/invalid`, { method: "DELETE" })
                  const json = await res.json()
                  if (json.success) {
                    toast({
                      title: "清理完成",
                      description: json.message || `已删除 ${json.count || 0} 个失效账号`
                    })
                    refetch()
                  } else {
                    throw new Error(json.message || '删除失败')
                  }
                } catch (e) {
                  toast({ variant: "destructive", title: "清理失败", description: String(e) })
                }
              }}
            >
              一键清理异常账号
            </Button>
          </div>
        }
      >
        <div className="flex flex-wrap gap-4">
          <Input
            ref={keywordInputRef}
            placeholder="输入名称或 ID 搜索..."
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            className="max-w-sm rounded-2xl border-white/10 bg-black text-white placeholder:text-white/40"
          />
          <div className="ml-auto">
            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as PlatformKey)}>
              <TabsList className="flex flex-wrap gap-2 rounded-2xl bg-black p-1 border border-white/10 backdrop-blur-sm">
                {platformTabs.map((tab) => (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="rounded-xl px-4 text-xs md:text-sm text-white/70 data-[state=active]:bg-white/90 data-[state=active]:text-black data-[state=active]:shadow-inner border border-transparent data-[state=active]:border-white/20 transition-colors"
                  >
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </div>

        {isLoading && (
          <div className="rounded-2xl border border-white/10 bg-black p-6 text-sm text-white/60">
            正在加载账号列表...
          </div>
        )}
        <DataTable columns={columns} data={filteredAccounts} pageSize={8} />
      </PageSection>
    </div>
  )
}
