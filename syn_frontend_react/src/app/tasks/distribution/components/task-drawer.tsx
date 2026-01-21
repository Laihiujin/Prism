"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { X, QrCode, Loader2, CheckCircle2, XCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import {
    Drawer,
    DrawerClose,
    DrawerContent,
    DrawerDescription,
    DrawerFooter,
    DrawerHeader,
    DrawerTitle,
} from "@/components/ui/drawer"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/components/ui/use-toast"
import { DatePicker } from "@/components/ui/date-picker"
import { TimePicker } from "@/components/ui/time-picker"
import { backendBaseUrl } from "@/lib/env"

interface DispatchTask {
    id: string
    platform: string
    title: string
    tags: string[]
    poi?: string
    expiryDate?: string
    materials: string[]
    status: 'pending' | 'dispatched' | 'published'
    assignedAccounts: number
    createdAt: string
}

interface TaskDrawerProps {
    task: DispatchTask
    open: boolean
    onOpenChange: (open: boolean) => void
    onTaskUpdate: () => void
}

interface QRSession {
    qrCode?: string
    platform: string
    status: 'pending' | 'scanned' | 'verified' | 'expired' | 'error'
}

export function TaskDrawer({ task, open, onOpenChange, onTaskUpdate }: TaskDrawerProps) {
    const { toast } = useToast()
    const queryClient = useQueryClient()

    const [selectedPlatform, setSelectedPlatform] = useState(task.platform)
    const [qrDrawerOpen, setQrDrawerOpen] = useState(false)
    const [qrSession, setQrSession] = useState<QRSession | null>(null)
    const eventSourceRef = useRef<EventSource | null>(null)
    const [verificationCode, setVerificationCode] = useState("")
    const [loginProgress, setLoginProgress] = useState(0)
    const [isLoggingIn, setIsLoggingIn] = useState(false)
    const [boundAccount, setBoundAccount] = useState<string | null>(null)
    const [selectedAccountId, setSelectedAccountId] = useState<string>("")
    const [publishDate, setPublishDate] = useState<string>()
    const [publishTime, setPublishTime] = useState<string>()
    const [loginSessionId, setLoginSessionId] = useState<string>("")

    const { data: accountsData, isFetching: isFetchingAccounts, refetch: refetchAccounts } = useQuery({
        queryKey: ["accounts"],
        queryFn: async () => {
            const res = await fetch("/api/accounts", { cache: "no-store" })
            const payload = await res.json().catch(() => ({}))
            return Array.isArray(payload?.data) ? payload.data : []
        },
        staleTime: 30_000,
    })

    const accounts = useMemo(() => (Array.isArray(accountsData) ? accountsData : []), [accountsData])
    const platformAccounts = useMemo(
        () => accounts.filter((a: any) => a.platform === selectedPlatform),
        [accounts, selectedPlatform]
    )

    useEffect(() => {
        if (!selectedAccountId) return
        const matched = accounts.find((acc: any) => acc.id === selectedAccountId)
        if (matched) {
            setBoundAccount(matched.name || matched.id)
        }
    }, [selectedAccountId, accounts])

    const platformToType = (platform: string) => {
        switch (platform) {
            case "redbook":
                return "1"
            case "tencent":
                return "2"
            case "douyin":
                return "3"
            case "kuaishou":
                return "4"
            case "bilibili":
                return "5"
            default:
                return ""
        }
    }

    const startQrLogin = () => {
        const type = platformToType(selectedPlatform)
        if (!type) {
            toast({ variant: "destructive", title: "不支持的平台" })
            return
        }

        // session id 同时作为备注，方便在账号列表中识别为派发账号
        const sessionId = `派发账号_${task.id}_${Date.now()}`
        setLoginSessionId(sessionId)

        // Clean up previous stream
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        setQrSession({ platform: selectedPlatform, status: "pending" })
        setQrDrawerOpen(true)
        setIsLoggingIn(false)
        setLoginProgress(0)
        setVerificationCode("")

        const es = new EventSource(`${backendBaseUrl}/api/login?type=${type}&id=${encodeURIComponent(sessionId)}`)
        eventSourceRef.current = es

        es.onmessage = (event) => {
            const data = event.data?.toString() || ""
            if (!data) return

            if (data === "200") {
                setQrSession((prev) => prev ? { ...prev, status: "verified" } : null)
                setLoginProgress(100)
                setIsLoggingIn(false)

                const findAccountWithRetry = async (retries = 3) => {
                    const result = await refetchAccounts()
                    const list = Array.isArray(result.data) ? result.data : []
                    const matched = list.find((acc: any) => {
                        const note = (acc?.note || "").toString()
                        return acc.platform === selectedPlatform && (note.includes(sessionId) || note.includes("派发"))
                    }) || list.find((acc: any) => acc.platform === selectedPlatform)

                    if (matched) {
                        const displayName = matched.name ? matched.name : `账号ID: ${matched.id}`
                        setBoundAccount(displayName)
                        setSelectedAccountId(String(matched.id))
                        toast({ title: "领取成功，请选择发布方式" })
                        return
                    }

                    if (retries > 0) {
                        await new Promise(resolve => setTimeout(resolve, 1000))
                        await findAccountWithRetry(retries - 1)
                    } else {
                        toast({ variant: "destructive", title: "领取成功但获取账号信息超时，请手动刷新" })
                    }
                }

                findAccountWithRetry()

                queryClient.invalidateQueries({ queryKey: ["accounts"] })
                setTimeout(() => {
                    setQrDrawerOpen(false)
                }, 500)
                es.close()
                eventSourceRef.current = null
                return
            }

            // Error
            if (data === "500") {
                setQrSession((prev) => prev ? { ...prev, status: "error" } : null)
                setIsLoggingIn(false)
                toast({ variant: "destructive", title: "登录失败，请重试" })
                es.close()
                eventSourceRef.current = null
                return
            }

            // Need verification code
            if (data.startsWith("VERIFY")) {
                setQrSession((prev) => prev ? { ...prev, status: "scanned" } : null)
                setIsLoggingIn(false)
                toast({ title: "请在下方输入验证码以继续" })
                return
            }

            // Otherwise treat as QR image URL
            setQrSession({ platform: selectedPlatform, status: "pending", qrCode: data })
        }

        es.onerror = () => {
            setQrSession((prev) => prev ? { ...prev, status: "error" } : null)
            setIsLoggingIn(false)
            toast({ variant: "destructive", title: "二维码连接中断，请重试" })
            es.close()
            eventSourceRef.current = null
        }
    }

    useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }
        }
    }, [])

    useEffect(() => {
        // reset drawer state when switching tasks
        setBoundAccount(null)
        setQrSession(null)
        setVerificationCode("")
        setLoginProgress(0)
        setIsLoggingIn(false)
        setQrDrawerOpen(false)
        setSelectedPlatform(task.platform)
        setSelectedAccountId("")
        setLoginSessionId("")
    }, [task])

    const sendVerificationCode = useMutation({
        mutationFn: async () => {
            if (!verificationCode || verificationCode.length !== 6) {
                throw new Error("请输入 6 位验证码")
            }
            setIsLoggingIn(true)
            setLoginProgress(40)

            const res = await fetch(`${backendBaseUrl}/api/v1/verification/submit-code`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ account_id: loginSessionId || task.id, code: verificationCode }),
            })

            if (!res.ok) {
                throw new Error("验证码提交失败")
            }

            setLoginProgress(90)
            return res.json()
        },
        onSuccess: () => {
            toast({ title: "验证码已提交，等待确认..." })
            setTimeout(() => {
                setLoginProgress(100)
            }, 400)
        },
        onError: (err) => {
            setIsLoggingIn(false)
            setLoginProgress(0)
            toast({ variant: "destructive", title: "提交验证码失败", description: String(err) })
        },
    })

    // Publish task
    const publishMutation = useMutation({
        mutationFn: async ({ immediate, accountId }: { immediate: boolean, accountId?: string }) => {
            const targetAccountId = accountId || selectedAccountId
            if (!targetAccountId) {
                throw new Error("请先扫码登录获取账号")
            }
            const scheduledAt = immediate ? undefined : `${publishDate || ""} ${publishTime || ""}`.trim()
            if (!immediate && (!publishDate || !publishTime)) {
                throw new Error("请先选择定时日期和时间")
            }
            const res = await fetch(`/api/dispatch-tasks/${task.id}/publish`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ immediate, scheduledAt, accountId: targetAccountId }),
            })
            if (!res.ok) throw new Error("Publish failed")
            return res.json()
        },
        onSuccess: () => {
            toast({ title: "发布成功" })
            onOpenChange(false)
            onTaskUpdate()
        },
        onError: (err) => {
            toast({ variant: "destructive", title: "发布失败", description: String(err) })
        },
    })

    const platformLabels: Record<string, string> = {
        douyin: "抖音",
        kuaishou: "快手",
        redbook: "小红书",
        bilibili: "B站",
        tencent: "视频号",
    }

    return (
        <>
            <Drawer open={open} onOpenChange={onOpenChange}>
                <DrawerContent className="bg-black border-white/10">
                    <DrawerHeader>
                        <DrawerTitle className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span>{task.title}</span>
                                <Badge variant="outline">{platformLabels[task.platform]}</Badge>
                            </div>
                            <DrawerClose asChild>
                                <Button variant="ghost" size="icon" className="rounded-xl">
                                    <X className="h-4 w-4" />
                                </Button>
                            </DrawerClose>
                        </DrawerTitle>
                        <DrawerDescription>
                            管理派发任务，选择平台并扫码绑定账号
                        </DrawerDescription>
                    </DrawerHeader>

                    <div className="px-4 py-6 space-y-6">
                        {/* Task Info */}
                        <div className="space-y-4">
                            <div>
                                <Label className="text-xs text-white/60">标签</Label>
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {task.tags.map((tag, i) => (
                                        <Badge key={i} variant="secondary">{tag}</Badge>
                                    ))}
                                </div>
                            </div>

                            {task.poi && (
                                <div>
                                    <Label className="text-xs text-white/60">POI 位置</Label>
                                    <p className="text-sm mt-1">{task.poi}</p>
                                </div>
                            )}

                            <div>
                                <Label className="text-xs text-white/60">素材数量</Label>
                                <p className="text-sm mt-1">{task.materials.length} 个视频</p>
                            </div>
                        </div>

                        {/* Platform Selection */}
                        <div className="space-y-2">
                            <Label>选择平台</Label>
                            <Select
                                value={selectedPlatform}
                                onValueChange={setSelectedPlatform}
                                disabled={!!boundAccount}
                            >
                                <SelectTrigger className="rounded-2xl /50 border-white/10">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-black border-white/10">
                                    <SelectItem value="douyin">抖音</SelectItem>
                                    <SelectItem value="kuaishou">快手</SelectItem>
                                    <SelectItem value="redbook">小红书</SelectItem>
                                    <SelectItem value="bilibili">B站</SelectItem>
                                    <SelectItem value="tencent">视频号</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {/* QR Dispatch Button */}
                        <Button
                            className="w-full rounded-2xl"
                            onClick={startQrLogin}
                            disabled={!!boundAccount}
                        >
                            <QrCode className="mr-2 h-4 w-4" />
                            QR派发
                        </Button>

                        {boundAccount && (
                            <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                                已绑定派发账号：{boundAccount}
                            </div>
                        )}

                        {/* Schedule Publish */}
                        <div className="space-y-4 pt-4 border-t border-white/10">
                            <Label>定时发布 (可选)</Label>
                            <div className="grid grid-cols-2 gap-4">
                                <DatePicker
                                    value={publishDate}
                                    onChange={setPublishDate}
                                    placeholder="选择日期"
                                />
                                <TimePicker
                                    value={publishTime}
                                    onChange={setPublishTime}
                                />
                            </div>
                        </div>
                    </div>

                    <DrawerFooter className="border-t border-white/10">
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                className="flex-1 rounded-2xl"
                                onClick={() => publishMutation.mutate({ immediate: false })}
                                disabled={!publishDate || !publishTime || publishMutation.isPending || (!selectedAccountId && !boundAccount)}
                            >
                                定时发布
                            </Button>
                            <Button
                                className="flex-1 rounded-2xl"
                                onClick={() => publishMutation.mutate({ immediate: true })}
                                disabled={publishMutation.isPending || (!selectedAccountId && !boundAccount)}
                            >
                                立即发布
                            </Button>
                        </div>
                    </DrawerFooter>
                </DrawerContent>
            </Drawer>

            {/* QR Login Drawer (Nested) */}
            <Drawer open={qrDrawerOpen} onOpenChange={setQrDrawerOpen}>
                <DrawerContent className="bg-black border-white/10">
                    <DrawerHeader>
                        <DrawerTitle>QR视频任务派发</DrawerTitle>
                        <DrawerDescription className="text-center">
                            使用{platformLabels[selectedPlatform]}扫码，一键领取并派发视频任务
                        </DrawerDescription>
                    </DrawerHeader>

                    <div className="px-4 py-6 space-y-6">
                        {/* QR Code & Verification stacked */}
                        <div className="flex flex-col items-center space-y-4">
                            {qrSession?.qrCode && (
                                <div className="bg-white p-4 rounded-2xl">
                                    <img
                                        src={qrSession.qrCode}
                                        alt="QR Code"
                                        className="w-64 h-64"
                                    />
                                </div>
                            )}

                            {/* Verification Code Input centered below QR */}
                            <div className="w-full max-w-xs space-y-2 text-center">
                                <Label className="text-sm text-white/80">验证码</Label>
                                <div className="w-full flex justify-center">
                                    <InputOTP
                                        maxLength={6}
                                        value={verificationCode}
                                        onChange={setVerificationCode}
                                        disabled={isLoggingIn}
                                    >
                                        <InputOTPGroup className="gap-2 justify-center w-full">
                                            <InputOTPSlot index={0} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                            <InputOTPSlot index={1} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                            <InputOTPSlot index={2} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                            <InputOTPSlot index={3} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                            <InputOTPSlot index={4} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                            <InputOTPSlot index={5} className="rounded-xl border-white/10 /50 text-white h-12 w-10" />
                                        </InputOTPGroup>
                                    </InputOTP>
                                </div>
                            </div>

                            {/* Status */}
                            <div className="flex items-center gap-2 text-sm">
                                {qrSession?.status === 'pending' && (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                                        <span className="text-white/60">等待扫码...</span>
                                    </>
                                )}
                                {qrSession?.status === 'scanned' && (
                                    <>
                                        <CheckCircle2 className="h-4 w-4 text-green-400" />
                                        <span className="text-green-400">已扫码，请确认</span>
                                    </>
                                )}
                                {qrSession?.status === 'expired' && (
                                    <>
                                        <XCircle className="h-4 w-4 text-red-400" />
                                        <span className="text-red-400">二维码已过期</span>
                                    </>
                                )}
                                {qrSession?.status === 'error' && (
                                    <>
                                        <XCircle className="h-4 w-4 text-red-400" />
                                        <span className="text-red-400">登录失败，请重试</span>
                                    </>
                                )}
                            </div>

                            {/* Progress Bar */}
                            {isLoggingIn && (
                                <div className="w-full max-w-xs space-y-2">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-white/60">登录进度</span>
                                        <span className="text-white">{loginProgress}%</span>
                                    </div>
                                    <Progress value={loginProgress} className="h-2" />
                                    <p className="text-xs text-white/50 text-center">
                                        {loginProgress < 30 && "正在验证..."}
                                        {loginProgress >= 30 && loginProgress < 60 && "正在获取账号信息..."}
                                        {loginProgress >= 60 && loginProgress < 90 && "正在绑定账号..."}
                                        {loginProgress >= 90 && loginProgress < 100 && "即将完成..."}
                                        {loginProgress === 100 && "领取成功！"}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    <DrawerFooter className="border-t border-white/10">
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                className="flex-1 rounded-2xl"
                                onClick={() => setQrDrawerOpen(false)}
                            >
                                取消
                            </Button>
                            <Button
                                className="flex-1 rounded-2xl"
                                onClick={() => sendVerificationCode.mutate()}
                                disabled={verificationCode.length !== 6 || sendVerificationCode.isPending || !loginSessionId}
                            >
                                {sendVerificationCode.isPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        验证中...
                                    </>
                                ) : (
                                    "登录领取派发任务"
                                )}
                            </Button>
                        </div>
                    </DrawerFooter>
                </DrawerContent>
            </Drawer>
        </>
    )
}
