"use client"

import { useState, useEffect } from "react"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { RefreshCcw, MonitorSmartphone, Globe, Network, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"

interface AccountEnvironmentSheetProps {
    accountId: string
    accountName: string
    platform: string
    open: boolean
    onOpenChange: (open: boolean) => void
}

interface EnvironmentData {
    account: Record<string, any>
    browser: Record<string, any>
    proxy: Record<string, any>
    identity: Record<string, any>
}

function FieldRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
    return (
        <div className="flex items-start justify-between gap-4 py-2 border-b border-border/50 last:border-0">
            <span className="text-xs text-muted-foreground shrink-0">{label}</span>
            <span className={cn("text-sm text-foreground/90 text-right", mono && "font-mono text-xs")}>{value || "-"}</span>
        </div>
    )
}

function ProxyStatusBadge({ status }: { status?: string }) {
    if (!status) return <Badge variant="outline" className="text-xs">未知</Badge>
    const map: Record<string, string> = {
        available: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        in_use: "bg-blue-500/15 text-blue-400 border-blue-500/30",
        degraded: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
        failed: "bg-red-500/15 text-red-400 border-red-500/30",
        banned: "bg-orange-500/15 text-orange-400 border-orange-500/30",
        auth_failed: "bg-red-500/15 text-red-400 border-red-500/30",
        checking: "bg-sky-500/15 text-sky-400 border-sky-500/30",
    }
    const label: Record<string, string> = {
        available: "健康",
        in_use: "占用中",
        degraded: "降级",
        failed: "离线",
        banned: "封禁",
        auth_failed: "认证失败",
        checking: "检测中",
    }
    return (
        <Badge variant="secondary" className={cn("text-xs", map[status])}>
            {label[status] || status}
        </Badge>
    )
}

export function AccountEnvironmentSheet({
    accountId,
    accountName,
    platform,
    open,
    onOpenChange,
}: AccountEnvironmentSheetProps) {
    const [data, setData] = useState<EnvironmentData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const load = async () => {
        if (!accountId) return
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`/api/v1/accounts/${encodeURIComponent(accountId)}/environment`)
            const json = await res.json()
            if (json.status === "success" && json.result) {
                setData(json.result)
            } else {
                setError(json.detail || "加载环境失败")
            }
        } catch (e) {
            setError(String(e))
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (open) load()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, accountId])

    const proxy = data?.proxy || {}
    const browser = data?.browser || {}
    const account = data?.account || {}

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="sm:max-w-md w-full flex flex-col p-6 bg-card border-l border-border/70">
                <SheetHeader className="mb-2">
                    <SheetTitle>账号环境 · {accountName || accountId}</SheetTitle>
                    <SheetDescription>
                        Account → Persona Profile → Sticky Proxy → Patchright → Platform Adapter
                    </SheetDescription>
                </SheetHeader>

                <div className="flex justify-end mb-2">
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg text-xs"
                        onClick={load}
                        disabled={loading}
                    >
                        <RefreshCcw className={cn("h-3 w-3 mr-1", loading && "animate-spin")} />
                        刷新
                    </Button>
                </div>

                {loading && (
                    <div className="space-y-3">
                        <div className="h-4 w-3/4 rounded bg-foreground/10 animate-pulse" />
                        <div className="h-4 w-1/2 rounded bg-foreground/10 animate-pulse" />
                        <div className="h-4 w-2/3 rounded bg-foreground/10 animate-pulse" />
                        <div className="h-4 w-1/3 rounded bg-foreground/10 animate-pulse" />
                    </div>
                )}

                {error && !loading && (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
                        {error}
                    </div>
                )}

                {!loading && !error && data && (
                    <div className="space-y-5 overflow-y-auto flex-1">
                        {/* 账号 */}
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <ShieldCheck className="h-4 w-4 text-primary" />
                                <h3 className="text-sm font-semibold">账号</h3>
                            </div>
                            <div className="rounded-xl border border-border/70 bg-foreground/5 px-4 py-1">
                                <FieldRow label="账号" value={account.name || accountName} />
                                <FieldRow label="平台" value={account.platform || platform} />
                                <FieldRow label="账号 ID" value={account.account_id} mono />
                                <FieldRow label="User ID" value={account.user_id} mono />
                            </div>
                        </div>

                        {/* 浏览器 */}
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <MonitorSmartphone className="h-4 w-4 text-primary" />
                                <h3 className="text-sm font-semibold">浏览器</h3>
                            </div>
                            <div className="rounded-xl border border-border/70 bg-foreground/5 px-4 py-1">
                                <FieldRow label="Backend" value={browser.backend || "patchright"} />
                                <FieldRow label="Engine" value={browser.engine || "Patchright Chromium"} />
                                <FieldRow label="Persona Profile" value={browser.persona_profile_id || "未分配"} mono />
                                <div className="flex items-start justify-between gap-4 py-2 border-b border-border/50 last:border-0">
                                    <span className="text-xs text-muted-foreground shrink-0">Persona 服务</span>
                                    {browser.persona_online ? (
                                        <Badge variant="secondary" className="text-xs bg-emerald-500/15 text-emerald-400 border-emerald-500/30">在线</Badge>
                                    ) : (
                                        <Badge variant="secondary" className="text-xs bg-yellow-500/15 text-yellow-400 border-yellow-500/30">
                                            离线 · 回退 Patchright
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* 代理 */}
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <Network className="h-4 w-4 text-primary" />
                                <h3 className="text-sm font-semibold">代理</h3>
                            </div>
                            <div className="rounded-xl border border-border/70 bg-foreground/5 px-4 py-1">
                                <FieldRow
                                    label="代理节点"
                                    value={proxy.name ? `${proxy.name} (${proxy.host}:${proxy.port})` : "未绑定"}
                                    mono
                                />
                                <FieldRow label="出口 IP" value={proxy.exit_ip} mono />
                                <FieldRow label="ASN" value={proxy.asn} mono />
                                <FieldRow label="ISP" value={proxy.isp} />
                                <FieldRow label="地区" value={[proxy.country, proxy.region, proxy.city].filter(Boolean).join(" ")} />
                                <FieldRow label="延迟" value={proxy.latency_ms != null ? `${proxy.latency_ms}ms` : "-"} />
                                <div className="flex items-start justify-between gap-4 py-2 border-b border-border/50 last:border-0">
                                    <span className="text-xs text-muted-foreground shrink-0">状态</span>
                                    <ProxyStatusBadge status={proxy.status} />
                                </div>
                                <FieldRow label="最后检测" value={proxy.last_check_at ? new Date(proxy.last_check_at).toLocaleString() : "-"} />
                            </div>
                        </div>

                        {/* 身份 */}
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <Globe className="h-4 w-4 text-primary" />
                                <h3 className="text-sm font-semibold">网络身份</h3>
                            </div>
                            <div className="rounded-xl border border-border/70 bg-foreground/5 px-4 py-1">
                                <FieldRow label="固定绑定" value={data.identity?.stable ? "是 (Sticky)" : "否"} />
                                {!data.identity?.stable && (
                                    <p className="py-2 text-xs text-yellow-400/90">
                                        该账号未绑定代理。国内平台可直连（network_mode=direct），海外平台需绑定代理。
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </SheetContent>
        </Sheet>
    )
}
