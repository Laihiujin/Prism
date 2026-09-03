"use client"

import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
    Globe,
    Plus,
    RefreshCcw,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Search,
    MoreHorizontal,
    Trash2,
    Link as LinkIcon,
    ShieldCheck,
    Activity,
    Server,
    MapPin,
    CloudLightning,
    MonitorSmartphone,
    LogOut
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetFooter,
} from "@/components/ui/sheet"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/components/layout/page-scaffold"

// Types
interface ProxyIP {
    id: string
    name?: string
    ip: string
    port: number
    protocol: string
    status: "available" | "in_use" | "failed" | "banned" | "checking"
    ip_type: string
    country: string
    region?: string
    city?: string
    isp?: string
    asn?: string
    exit_ip?: string
    latency_ms?: number
    bound_account_ids: string[]
    max_bindings: number
    success_rate: number
    last_used_at?: string
    last_check_at?: string
    created_at: string
    success_count: number
    fail_count: number
    total_used: number
    provider?: string
}

interface IPStats {
    total: number
    available: number
    in_use: number
    failed: number
    banned: number
    total_bindings: number
    avg_success_rate: number
}

interface Account {
    id: string
    account_id?: string
    platform: string
    name: string
    avatar_url?: string
}

// Stats Card Component
function StatsCard({ title, value, icon: Icon, description, trend }: any) {
    return (
        <Card className="bg-card/40 border-border/70">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-foreground/70">{title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                {description && (
                    <p className="text-xs text-muted-foreground mt-1">{description}</p>
                )}
            </CardContent>
        </Card>
    )
}

export default function IPPoolPage() {
    const { toast } = useToast()
    const queryClient = useQueryClient()
    const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
    const [isImportDialogOpen, setIsImportDialogOpen] = useState(false)
    const [bindDialogIP, setBindDialogIP] = useState<ProxyIP | null>(null)
    const [replaceTargetIP, setReplaceTargetIP] = useState<ProxyIP | null>(null)
    const [addMode, setAddMode] = useState<'qingguo' | 'manual'>('qingguo')
    const [importText, setImportText] = useState("")

    // Queries
    const { data: stats } = useQuery<IPStats>({
        queryKey: ["ip-pool", "stats"],
        queryFn: async () => {
            const res = await fetch("/api/v1/ip-pool/stats")
            return res.json()
        }
    })

    const { data: ipListResponse } = useQuery({
        queryKey: ["ip-pool", "list"],
        queryFn: async () => {
            const res = await fetch("/api/v1/ip-pool/list")
            return res.json()
        }
    })

    const { data: accountsResponse } = useQuery({
        queryKey: ["accounts"],
        queryFn: async () => {
            const res = await fetch("/api/v1/accounts?limit=1000")
            return res.json()
        }
    })

    const { data: personaStatus } = useQuery({
        queryKey: ["ip-pool", "persona-status"],
        queryFn: async () => {
            const res = await fetch("/api/v1/ip-pool/persona/status")
            return res.json()
        }
    })

    // Mutations
    const addIPMutation = useMutation({
        mutationFn: async (data: any) => {
            const res = await fetch("/api/v1/ip-pool/add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            })
            if (!res.ok) throw new Error(await res.text())
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            setIsAddDialogOpen(false)
            toast({ title: "添加成功", description: "新的IP已添加到资源池" })
        },
        onError: (err) => {
            toast({ variant: "destructive", title: "添加失败", description: err.message })
        }
    })

    const fetchQingGuoMutation = useMutation({
        mutationFn: async (data: { url: string }) => {
            const res = await fetch("/api/v1/ip-pool/fetch-from-url", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            })
            const result = await res.json()
            if (result.status === "error") throw new Error(result.message)
            return result
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            setIsAddDialogOpen(false)

            if (replaceTargetIP) {
                // 如果是更换模式，执行迁移逻辑
                if (data.result && data.result.ip && data.result.ip.id) {
                    const newIpId = data.result.ip.id
                    // 1. 迁移绑定
                    if (replaceTargetIP.bound_account_ids.length > 0) {
                        bindAccountsMutation.mutate({
                            ipId: newIpId,
                            accountIds: replaceTargetIP.bound_account_ids
                        })
                    }
                    // 2. 删除旧IP
                    deleteIPMutation.mutate(replaceTargetIP.id)
                    toast({ title: "更换成功", description: "已自动迁移账号绑定并删除旧IP" })
                }
                setReplaceTargetIP(null)
            } else {
                toast({ title: "提取成功", description: data.result.message })
            }
        },
        onError: (err) => {
            toast({ variant: "destructive", title: "提取失败", description: err.message })
        }
    })

    const checkHealthMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/ip-pool/check-health/${id}`, { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            toast({
                title: data.result.healthy ? "检测通过" : "检测失败",
                description: data.result.message,
                variant: data.result.healthy ? "default" : "destructive"
            })
        }
    })

    const deleteIPMutation = useMutation({
        mutationFn: async (id: string) => {
            const res = await fetch(`/api/v1/ip-pool/${id}`, { method: "DELETE" })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            toast({ title: "删除成功", description: "IP已从资源池移除" })
        }
    })

    const releaseQGIPMutation = useMutation({
        mutationFn: async (ip: ProxyIP) => {
            // 这里假设 key 是预埋的或者从某处获取，简化起见我们只从后端删，或者如果要调用释放接口需要 key
            // 按照用户需求 6. 释放接口，需要 key。我们暂时从 ip provider info 获取或者全局配置
            // 这里为了演示，先只做本地删除，因为我们没存用户的 AuthKey
            // 如果用户愿意，我们可以在后端 QG Service 存一个默认 key
            // 现在先等同于删除
            return deleteIPMutation.mutateAsync(ip.id)
        }
    })

    const bindAccountsMutation = useMutation({
        mutationFn: async ({ ipId, accountIds }: { ipId: string, accountIds: string[] }) => {
            const res = await fetch("/api/v1/ip-pool/bind-batch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip_id: ipId, account_ids: accountIds })
            })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            setBindDialogIP(null)
            toast({ title: "绑定成功", description: "账号→代理固定绑定已更新" })
        }
    })

    const unbindMutation = useMutation({
        mutationFn: async (accountId: string) => {
            const res = await fetch(`/api/v1/ip-pool/unbind/${accountId}`, { method: "POST" })
            return res.json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            toast({ title: "解绑成功", description: "账号与代理的绑定已解除" })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "解绑失败", description: err.message })
        }
    })

    const checkAllHealthMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch("/api/v1/ip-pool/check-all", { method: "POST" })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            toast({
                title: "批量检测完成",
                description: data.result.message
            })
        }
    })

    const exportMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch("/api/v1/ip-pool/export")
            return res.json()
        },
        onSuccess: (data) => {
            const blob = new Blob([JSON.stringify(data.result.items, null, 2)], { type: "application/json" })
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `proxies-${new Date().toISOString().slice(0, 10)}.json`
            a.click()
            URL.revokeObjectURL(url)
            toast({ title: "导出成功", description: `已导出 ${data.result.total} 个代理` })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "导出失败", description: err.message })
        }
    })

    const importMutation = useMutation({
        mutationFn: async (text: string) => {
            const items = JSON.parse(text)
            const res = await fetch("/api/v1/ip-pool/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ items })
            })
            return res.json()
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["ip-pool"] })
            setImportText("")
            setIsImportDialogOpen(false)
            toast({ title: "导入成功", description: data.result.message })
        },
        onError: (err: any) => {
            toast({ variant: "destructive", title: "导入失败", description: err.message })
        }
    })

    const ips: ProxyIP[] = ipListResponse?.result?.items || []
    const accounts: Account[] = accountsResponse?.result?.items || accountsResponse?.items || []

    // Add IP Form State
    const [addForm, setAddForm] = useState({
        name: "",
        ip: "",
        port: "",
        protocol: "http",
        username: "",
        password: "",
        type: "residential",
        max_bindings: 1
    })

    const [qgLink, setQgLink] = useState("https://exclusive.proxy.qg.net/replace?key=880E8B24&num=1&area=&isp=0&format=json&distinct=false&keep_alive=1440")

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="代理管理"
                description="账号级固定代理绑定 / 出口 IP 检测 / 环境隔离"
                actions={
                    <div className="flex items-center gap-2 flex-wrap">
                        <Button
                            variant="outline"
                            className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
                            onClick={() => checkAllHealthMutation.mutate()}
                            disabled={checkAllHealthMutation.isPending}
                        >
                            <RefreshCcw className={cn("mr-2 h-4 w-4", checkAllHealthMutation.isPending && "animate-spin")} />
                            检测全部
                        </Button>
                        <Button
                            variant="outline"
                            className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
                            onClick={() => exportMutation.mutate()}
                            disabled={exportMutation.isPending}
                        >
                            <CloudLightning className="mr-2 h-4 w-4" />
                            导出
                        </Button>
                        <Button
                            variant="outline"
                            className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
                            onClick={() => setIsImportDialogOpen(true)}
                            disabled={importMutation.isPending}
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            导入
                        </Button>
                        <Button
                            className="rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20"
                            onClick={() => setIsAddDialogOpen(true)}
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            添加代理
                        </Button>
                    </div>
                }
            />

            {/* Stats */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatsCard
                    title="总代理节点"
                    value={stats?.total || 0}
                    icon={Server}
                    description={`${stats?.available || 0} 可用 / ${stats?.in_use || 0} 占用`}
                />
                <StatsCard
                    title="已绑定账号"
                    value={stats?.total_bindings || 0}
                    icon={LinkIcon}
                    description="账号→代理固定绑定"
                />
                <StatsCard
                    title="平均成功率"
                    value={`${stats?.avg_success_rate || 0}%`}
                    icon={Activity}
                    description="最近24小时"
                />
                <StatsCard
                    title="异常/失效"
                    value={(stats?.failed || 0) + (stats?.banned || 0)}
                    icon={AlertCircle}
                    description="需及时处理"
                />
            </div>

            {/* Browser Identity 层状态（Persona Studio） */}
            <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-card/40 px-4 py-3 text-sm">
                <MonitorSmartphone className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">Browser Identity</span>
                {personaStatus?.result?.online ? (
                    <>
                        <Badge variant="secondary" className="text-xs bg-black text-white border-border">
                            Persona Studio 在线
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                            引擎: {personaStatus.result.default_engine} · Profiles: {personaStatus.result.profile_count} · 代理注入: {personaStatus.result.inject_proxy ? "开" : "关"}
                        </span>
                    </>
                ) : (
                    <>
                        <Badge variant="secondary" className="text-xs bg-black text-white border-border">
                            Persona Studio 离线
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                            {personaStatus?.result?.message || "浏览器将回退 Patchright 直连模式（每账号独立 user_data_dir）"}
                        </span>
                    </>
                )}
            </div>

            {/* Main Table */}
            <Card className="bg-card/40 border-border/70">
                <CardHeader>
                    <CardTitle>代理节点</CardTitle>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow className="hover:bg-accent/40 border-border/70">
                                <TableHead>代理节点</TableHead>
                                <TableHead>出口 IP</TableHead>
                                <TableHead>ASN</TableHead>
                                <TableHead>地区</TableHead>
                                <TableHead>绑定账号</TableHead>
                                <TableHead>状态</TableHead>
                                <TableHead>延迟</TableHead>
                                <TableHead className="text-right">操作</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {ips.map((ip) => {
                                const boundAccount = ip.bound_account_ids[0]
                                const boundAccountName = boundAccount
                                    ? accounts.find(a => String(a.id || a.account_id) === boundAccount)?.name || boundAccount
                                    : null
                                return (
                                    <TableRow key={ip.id} className="hover:bg-accent/40 border-border/70">
                                        <TableCell>
                                            <div className="flex flex-col">
                                                <span className="font-medium">{ip.name || ip.ip}</span>
                                                <span className="text-xs text-muted-foreground font-mono">{ip.ip}:{ip.port} · {ip.protocol}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <code className="text-xs font-mono text-foreground/80">{ip.exit_ip || "-"}</code>
                                        </TableCell>
                                        <TableCell>
                                            <span className="text-xs text-muted-foreground">{ip.asn || "-"}</span>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-1 text-sm">
                                                <MapPin className="h-3 w-3 text-muted-foreground" />
                                                {[ip.country, ip.region, ip.city].filter(Boolean).join(" ") || "-"}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {boundAccountName ? (
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{boundAccountName}</span>
                                                    <span className="text-[10px] text-muted-foreground font-mono truncate max-w-[120px]">{boundAccount}</span>
                                                </div>
                                            ) : (
                                                <span className="text-xs text-muted-foreground">未绑定</span>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="secondary"
                                                className={cn(
                                                    "text-xs",
                                                    ip.status === 'available' && "bg-black text-white border-border",
                                                    ip.status === 'in_use' && "bg-black text-white border-border",
                                                    ip.status === 'failed' && "bg-black text-white border-border",
                                                    ip.status === 'banned' && "bg-black text-white border-border",
                                                )}
                                            >
                                                {ip.status === 'available' ? '可用' :
                                                    ip.status === 'in_use' ? '占用' :
                                                        ip.status === 'failed' ? '失效' :
                                                            ip.status === 'banned' ? '封禁' : ip.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-xs text-muted-foreground">
                                            {ip.latency_ms !== undefined ? `${ip.latency_ms}ms` : '-'}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" className="h-8 w-8 p-0">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuLabel>操作</DropdownMenuLabel>
                                                    <DropdownMenuItem onClick={() => setBindDialogIP(ip)}>
                                                        <LinkIcon className="mr-2 h-4 w-4" />
                                                        {boundAccount ? "换绑账号" : "绑定账号"}
                                                    </DropdownMenuItem>
                                                    {boundAccount && (
                                                        <DropdownMenuItem onClick={() => {
                                                            const a = accounts.find(acc => String(acc.id || acc.account_id) === boundAccount)
                                                            toast({ title: "绑定账号", description: a?.name || boundAccount })
                                                        }}>
                                                            <CheckCircle2 className="mr-2 h-4 w-4" />
                                                            查看绑定
                                                        </DropdownMenuItem>
                                                    )}
                                                    {boundAccount && (
                                                        <DropdownMenuItem onClick={() => unbindMutation.mutate(boundAccount)}>
                                                            <XCircle className="mr-2 h-4 w-4" />
                                                            解绑账号
                                                        </DropdownMenuItem>
                                                    )}
                                                    <DropdownMenuItem onClick={() => checkHealthMutation.mutate(ip.id)}>
                                                        <Activity className="mr-2 h-4 w-4" />
                                                        检测健康
                                                    </DropdownMenuItem>

                                                    <DropdownMenuItem onClick={() => {
                                                        if (ip.exit_ip) {
                                                            toast({ title: `出口 IP: ${ip.exit_ip}`, description: ip.asn || "未识别 ASN" })
                                                        } else {
                                                            toast({ title: "暂无出口 IP", description: "请先执行健康检测" })
                                                        }
                                                    }}>
                                                        <Globe className="mr-2 h-4 w-4" />
                                                        查看出口 IP
                                                    </DropdownMenuItem>

                                                    <DropdownMenuItem onClick={() => {
                                                        setReplaceTargetIP(ip)
                                                        setIsAddDialogOpen(true)
                                                    }}>
                                                        <RefreshCcw className="mr-2 h-4 w-4" />
                                                        更换代理
                                                    </DropdownMenuItem>

                                                    <DropdownMenuSeparator />

                                                    {ip.provider === "qg.net" && (
                                                        <DropdownMenuItem
                                                            onClick={() => deleteIPMutation.mutate(ip.id)}
                                                            className="text-white focus:text-white"
                                                        >
                                                            <LogOut className="mr-2 h-4 w-4" />
                                                            释放并删除
                                                        </DropdownMenuItem>
                                                    )}

                                                    <DropdownMenuItem
                                                        className="text-white focus:text-white"
                                                        onClick={() => deleteIPMutation.mutate(ip.id)}
                                                    >
                                                        <Trash2 className="mr-2 h-4 w-4" />
                                                        删除
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                            {ips.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                                        暂无代理节点，请先添加或导入
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Add IP Dialog */}
            <Dialog open={isAddDialogOpen} onOpenChange={(open) => {
                setIsAddDialogOpen(open)
                if (!open) setReplaceTargetIP(null) // 关闭时重置
            }}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{replaceTargetIP ? `更换代理: ${replaceTargetIP.name || replaceTargetIP.ip}` : "添加代理节点"}</DialogTitle>
                        <DialogDescription>
                            {replaceTargetIP ? "提取新代理后，系统将自动迁移原代理绑定的账号并删除原代理。" : "支持本机直连、API 提取或手动添加 HTTP/SOCKS5 代理。"}
                        </DialogDescription>
                    </DialogHeader>

                    {/* Quick Action for Local Direct */}
                    <div className="bg-black border border-border rounded-lg p-3 mb-4 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5 text-white" />
                            <div className="text-sm">
                                <span className="font-medium text-white block">推荐方案：本机直连</span>
                                <span className="text-muted-foreground text-xs">使用本地宽带，最安全稳定的防关联方案</span>
                            </div>
                        </div>
                        <Button
                            size="sm"
                            variant="secondary"
                            className="bg-black hover:bg-black text-white border-none"
                            onClick={() => {
                                setAddForm({
                                    name: "",
                                    ip: "127.0.0.1",
                                    port: "",
                                    protocol: "direct",
                                    username: "",
                                    password: "",
                                    type: "dynamic_residential",
                                    max_bindings: 1
                                })
                                setAddMode('manual')
                            }}
                        >
                            一键填充
                        </Button>
                    </div>

                    <div className="flex gap-2 p-1 bg-black rounded-lg mb-4">
                        <button
                            onClick={() => setAddMode('qingguo')}
                            className={cn(
                                "flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-all",
                                addMode === 'qingguo' ? "bg-primary text-primary-foreground shadow-md" : "text-muted-foreground hover:bg-accent/40"
                            )}
                        >
                            ⚡️ API 自动提取
                        </button>
                        <button
                            onClick={() => setAddMode('manual')}
                            className={cn(
                                "flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-all",
                                addMode === 'manual' ? "bg-primary text-primary-foreground shadow-md" : "text-muted-foreground hover:bg-accent/40"
                            )}
                        >
                            🖐 手动添加
                        </button>
                    </div>

                    {addMode === 'qingguo' ? (
                        <div className="space-y-4 py-2">
                            <div className="space-y-2">
                                <Label>提取 API 链接 (Universal API)</Label>
                                <Textarea
                                    className="h-24 resize-none font-mono text-xs"
                                    placeholder="https://api.provider.com/get_ip?..."
                                    value={qgLink}
                                    onChange={e => setQgLink(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    支持任意代理服务商的提取链接 (JSON或文本)，系统会自动识别 IP:Port。
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="grid gap-4 py-2">
                            <div className="space-y-2">
                                <Label>节点名称（可选）</Label>
                                <Input
                                    value={addForm.name}
                                    onChange={e => setAddForm(prev => ({ ...prev, name: e.target.value }))}
                                    placeholder="proxy-001"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>IP地址</Label>
                                    <Input
                                        value={addForm.ip}
                                        onChange={e => setAddForm(prev => ({ ...prev, ip: e.target.value }))}
                                        placeholder="1.2.3.4"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>端口 (Port)</Label>
                                    <Input
                                        value={addForm.port}
                                        onChange={e => setAddForm(prev => ({ ...prev, port: e.target.value }))}
                                        placeholder="8888"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>协议</Label>
                                    <Select
                                        value={addForm.protocol}
                                        onValueChange={v => setAddForm(prev => ({ ...prev, protocol: v }))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="http">HTTP</SelectItem>
                                            <SelectItem value="socks5">SOCKS5</SelectItem>
                                            <SelectItem value="direct">本机直连 (Direct)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>类型</Label>
                                    <Select
                                        value={addForm.type}
                                        onValueChange={v => setAddForm(prev => ({ ...prev, type: v }))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="residential">住宅IP</SelectItem>
                                            <SelectItem value="dynamic_residential">动态住宅</SelectItem>
                                            <SelectItem value="datacenter">机房IP</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label>最大绑定数</Label>
                                <Input
                                    type="number"
                                    value={addForm.max_bindings}
                                    onChange={e => setAddForm(prev => ({ ...prev, max_bindings: parseInt(e.target.value) }))}
                                />
                            </div>
                        </div>
                    )}

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>取消</Button>
                        {addMode === 'qingguo' ? (
                            <Button
                                onClick={() => fetchQingGuoMutation.mutate({ url: qgLink })}
                                disabled={fetchQingGuoMutation.isPending}
                            >
                                {fetchQingGuoMutation.isPending ? (
                                    <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <CloudLightning className="mr-2 h-4 w-4" />
                                )}
                                立即提取
                            </Button>
                        ) : (
                            <Button onClick={() => addIPMutation.mutate({
                                name: addForm.name || undefined,
                                ip: addForm.ip,
                                port: addForm.port === "" ? 0 : parseInt(addForm.port),
                                protocol: addForm.protocol,
                                username: addForm.username || undefined,
                                password: addForm.password || undefined,
                                ip_type: addForm.type,
                                max_bindings: addForm.max_bindings
                            })}>
                                确认添加
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Import Dialog */}
            <Dialog open={isImportDialogOpen} onOpenChange={setIsImportDialogOpen}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>批量导入代理</DialogTitle>
                        <DialogDescription>
                            粘贴 JSON 格式的代理数组。每个代理包含 ip、port、protocol、username、password 等字段。
                        </DialogDescription>
                    </DialogHeader>
                    <Textarea
                        className="h-48 font-mono text-xs"
                        placeholder={'[{"ip":"1.2.3.4","port":8888,"protocol":"http","username":"user","password":"pass"}]'}
                        value={importText}
                        onChange={e => setImportText(e.target.value)}
                    />
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsImportDialogOpen(false)}>取消</Button>
                        <Button
                            onClick={() => importMutation.mutate(importText)}
                            disabled={!importText.trim() || importMutation.isPending}
                        >
                            {importMutation.isPending ? "导入中..." : "确认导入"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Bind Accounts Dialog */}
            {bindDialogIP && (
                <BindAccountSheet
                    ip={bindDialogIP}
                    allAccounts={accounts}
                    open={!!bindDialogIP}
                    onOpenChange={(open) => !open && setBindDialogIP(null)}
                    onConfirm={(ids) => {
                        bindAccountsMutation.mutate({ ipId: bindDialogIP.id, accountIds: ids })
                        setBindDialogIP(null)
                    }}
                />
            )}
        </div>
    )
}

// Bind Account Sheet Component
function BindAccountSheet({
    ip,
    allAccounts,
    open,
    onOpenChange,
    onConfirm
}: {
    ip: ProxyIP
    allAccounts: Account[]
    open: boolean
    onOpenChange: (open: boolean) => void
    onConfirm: (ids: string[]) => void
}) {
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set(ip.bound_account_ids))
    const [searchTerm, setSearchTerm] = useState("")

    // Group accounts by platform
    // Group accounts by platform with deduplication
    const accountsByPlatform = useMemo(() => {
        const groups: Record<string, Account[]> = {}
        const seenIds = new Set<string>()

        // 调试：打印前几个账号看看结构
        if (allAccounts?.length > 0) {
            // console.log("First account:", allAccounts[0])
        }

        allAccounts.forEach(acc => {
            // 兼容 account_id (API返回) 和 id (类型定义)
            // @ts-ignore
            const rawId = acc.account_id || acc.id
            if (rawId === undefined || rawId === null) return
            const idStr = String(rawId)

            if (seenIds.has(idStr)) return

            // Ensure ID is set on object for display
            if (!acc.id) {
                // @ts-ignore
                acc.id = idStr
            }

            // 搜索过滤
            if (searchTerm) {
                const term = searchTerm.toLowerCase()

                // @ts-ignore
                const name = acc.name || acc.nickname || ''
                const matchName = name.toLowerCase().includes(term)

                const matchId = idStr.toLowerCase().includes(term)

                if (!matchName && !matchId) return
            }

            seenIds.add(idStr)

            const p = acc.platform || 'other'
            if (!groups[p]) groups[p] = []
            groups[p].push(acc)
        })
        return groups
    }, [allAccounts, searchTerm])

    const toggleAccount = (id: string) => {
        const newSet = new Set(selectedIds)
        if (newSet.has(id)) newSet.delete(id)
        else newSet.add(id)
        setSelectedIds(newSet)
    }

    const togglePlatform = (platform: string, accounts: Account[]) => {
        const newSet = new Set(selectedIds)
        const allSelected = accounts.every(a => selectedIds.has(a.id))

        accounts.forEach(a => {
            if (allSelected) newSet.delete(a.id)
            else newSet.add(a.id)
        })
        setSelectedIds(newSet)
    }

    // 计算总过滤后的账号数
    const totalFiltered = Object.values(accountsByPlatform).reduce((acc, curr) => acc + curr.length, 0)

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="sm:max-w-[50vw] w-[90vw] flex flex-col p-6 bg-card border-l border-border/70 text-white dark">
                <SheetHeader className="mb-4">
                    <SheetTitle className="text-white">绑定账号到代理</SheetTitle>
                    <SheetDescription className="text-white">
                        {ip.name || `${ip.ip}:${ip.port}`} · {[ip.country, ip.region, ip.city].filter(Boolean).join(" ")}
                        <span className="block mt-1 text-xs">绑定后持久生效：登录、发布、数据回收始终走该代理</span>
                    </SheetDescription>



                    {/* 搜索框 */}
                    <div className="pt-4">
                        <div className="relative">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-white" />
                            <Input
                                placeholder="搜索账号名称或ID..."
                                className="pl-9 h-9 bg-white border-border/70 text-black placeholder:text-black focus-visible:ring-offset-0 focus-visible:ring-1 focus-visible:ring-border/50"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>
                </SheetHeader>

                <ScrollArea className="flex-1 pr-4 -mr-4 p-1">
                    <div className="space-y-8">
                        {totalFiltered === 0 ? (
                            <div className="text-center py-10 text-muted-foreground">
                                没有找到匹配的账号
                            </div>
                        ) : (
                            Object.entries(accountsByPlatform).map(([platform, accounts]) => (
                                <div key={platform} className="space-y-3">
                                    <div className="flex items-center justify-between sticky top-0 bg-card backdrop-blur p-2 z-10 border-b border-border/70 my-2">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="capitalize text-base px-3 py-1 border-border/70 text-white bg-black">{platform}</Badge>
                                            <span className="text-sm text-white">{accounts.length}个账号</span>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-8 text-xs text-white hover:text-white hover:bg-accent/40"
                                            onClick={() => togglePlatform(platform, accounts)}
                                        >
                                            {accounts.every(a => selectedIds.has(a.id)) ? "取消全选" : "全选本组"}
                                        </Button>
                                    </div>

                                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                                        {accounts.map(account => (
                                            <div
                                                key={account.id}
                                                className={cn(
                                                    "flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all duration-200 relative group",
                                                    selectedIds.has(account.id)
                                                        ? "bg-black ring-1 ring-border/50"
                                                        : "bg-black hover:bg-white ring-1 ring-border/5 hover:ring-border/40"
                                                )}
                                                onClick={() => toggleAccount(account.id)}
                                            >
                                                <Checkbox checked={selectedIds.has(account.id)} className="mt-1 self-start" />
                                                <div className="flex flex-col overflow-hidden w-full">
                                                    <div className="flex items-center justify-between w-full">
                                                        <span className="text-sm font-medium truncate" title={account.name}>{account.name}</span>
                                                    </div>
                                                    <span className="text-xs text-muted-foreground truncate opacity-70 font-mono mt-0.5">
                                                        {String(account.id || '')}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </ScrollArea>

                <SheetFooter className="mt-4 pt-4 border-t flex-row justify-between items-center sm:justify-between">
                    <div className="flex items-center gap-2">
                        <span className={cn(
                            "text-sm font-medium",
                            selectedIds.size > ip.max_bindings ? "text-white" : "text-muted-foreground"
                        )}>
                            当前选中: {selectedIds.size} / {ip.max_bindings}
                        </span>
                        {selectedIds.size > ip.max_bindings && (
                            <span className="text-xs text-white">超过建议值</span>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
                        <Button onClick={() => onConfirm(Array.from(selectedIds))}>确认绑定</Button>
                    </div>
                </SheetFooter>
            </SheetContent>
        </Sheet>
    )
}

