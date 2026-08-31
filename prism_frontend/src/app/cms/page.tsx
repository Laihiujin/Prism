"use client"

import { useEffect, useState } from "react"
import {
    Loader2,
    Save,
    RefreshCcw,
    Server,
    Bug,
    ShieldCheck,
    Database,
    Globe,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/layout/page-scaffold"
import { cn } from "@/lib/utils"

interface CmsSettings {
    douyinLoginMode: string
    browserBackend: string
    headless: boolean
}

export default function CmsPage() {
    const { toast } = useToast()
    const [settings, setSettings] = useState<CmsSettings>({
        douyinLoginMode: "browser",
        browserBackend: "patchright",
        headless: true,
    })
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState<string | null>(null)

    const load = async () => {
        setLoading(true)
        try {
            const [modeRes, headlessRes] = await Promise.all([
                fetch("/api/v1/system/douyin-login-mode", { cache: "no-store" }),
                fetch("/api/v1/system/browser-headless", { cache: "no-store" }),
            ])
            const mode = await modeRes.json().catch(() => ({}))
            const headless = await headlessRes.json().catch(() => ({}))
            setSettings((s) => ({
                ...s,
                douyinLoginMode: mode?.mode || s.douyinLoginMode,
                headless: headless?.headless ?? s.headless,
            }))
        } catch (err) {
            toast({ variant: "destructive", title: "加载失败", description: String(err) })
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        void load()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const saveDouyinMode = async (mode: string) => {
        setSaving("douyin")
        try {
            const res = await fetch("/api/v1/system/douyin-login-mode", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode }),
            })
            const payload = await res.json().catch(() => ({}))
            if (!res.ok) throw new Error(payload?.detail || "保存失败")
            setSettings((s) => ({ ...s, douyinLoginMode: mode }))
            toast({
                title: "抖音登录模式已保存",
                description: mode === "http" ? "逆向 HTTP（测试）· 需重启后端生效" : "浏览器（正式/当前模拟）· 需重启后端生效",
            })
        } catch (err) {
            toast({ variant: "destructive", title: "保存失败", description: String(err) })
        } finally {
            setSaving(null)
        }
    }

    const saveHeadless = async (headless: boolean) => {
        setSaving("headless")
        try {
            const res = await fetch("/api/v1/system/browser-headless", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ headless }),
            })
            const payload = await res.json().catch(() => ({}))
            if (!res.ok) throw new Error(payload?.detail || "保存失败")
            setSettings((s) => ({ ...s, headless }))
            toast({ title: "无头模式已保存", description: "需重启后端生效" })
        } catch (err) {
            toast({ variant: "destructive", title: "保存失败", description: String(err) })
        } finally {
            setSaving(null)
        }
    }

    const OptionButton = ({
        active,
        label,
        icon: Icon,
        onClick,
        disabled,
    }: {
        active: boolean
        label: string
        icon: any
        onClick: () => void
        disabled?: boolean
    }) => (
        <button
            onClick={onClick}
            disabled={disabled}
            className={cn(
                "flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm transition",
                active
                    ? "border-border/80 bg-black text-foreground"
                    : "border-border/70 bg-card/40 text-muted-foreground hover:bg-accent/40"
            )}
        >
            <Icon className="h-4 w-4" />
            {label}
        </button>
    )

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="CMS 后台"
                description="系统运行配置与管理：登录模式、浏览器行为等"
                actions={
                    <Button
                        variant="outline"
                        className="rounded-xl border-border/70 bg-black hover:bg-accent/50"
                        onClick={() => void load()}
                    >
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                }
            />

            {loading ? (
                <div className="flex items-center gap-2 py-12 text-muted-foreground text-sm">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    加载配置...
                </div>
            ) : (
                <div className="grid gap-6 lg:grid-cols-2">
                    {/* 抖音登录模式 */}
                    <Card className="border-border/70 bg-card">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Bug className="h-4 w-4" />
                                抖音登录模式
                            </CardTitle>
                            <CardDescription className="text-muted-foreground">
                                选择抖音登录实现：默认「浏览器（正式/当前模拟）」；「逆向 HTTP」为测试路径，确认可用后再切换。修改后需重启后端生效。
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-wrap gap-3">
                                <OptionButton
                                    active={settings.douyinLoginMode === "browser"}
                                    label="浏览器（正式 / 当前模拟）"
                                    icon={Globe}
                                    onClick={() => void saveDouyinMode("browser")}
                                    disabled={saving === "douyin"}
                                />
                                <OptionButton
                                    active={settings.douyinLoginMode === "http"}
                                    label="逆向 HTTP（测试）"
                                    icon={Bug}
                                    onClick={() => void saveDouyinMode("http")}
                                    disabled={saving === "douyin"}
                                />
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <Badge variant="outline">
                                    当前：{settings.douyinLoginMode === "http" ? "逆向 HTTP（测试）" : "浏览器（正式）"}
                                </Badge>
                                {saving === "douyin" && <Loader2 className="h-4 w-4 animate-spin" />}
                            </div>
                        </CardContent>
                    </Card>

                    {/* 无头模式 */}
                    <Card className="border-border/70 bg-card">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Server className="h-4 w-4" />
                                浏览器无头模式
                            </CardTitle>
                            <CardDescription className="text-muted-foreground">
                                后台运行（无头）或弹出可见浏览器窗口。修改后需重启后端生效。
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-wrap gap-3">
                                <OptionButton
                                    active={settings.headless === true}
                                    label="无头（后台运行）"
                                    icon={ShieldCheck}
                                    onClick={() => void saveHeadless(true)}
                                    disabled={saving === "headless"}
                                />
                                <OptionButton
                                    active={settings.headless === false}
                                    label="有头（显示窗口）"
                                    icon={Globe}
                                    onClick={() => void saveHeadless(false)}
                                    disabled={saving === "headless"}
                                />
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <Badge variant="outline">
                                    当前：{settings.headless ? "无头（后台）" : "有头（显示窗口）"}
                                </Badge>
                                {saving === "headless" && <Loader2 className="h-4 w-4 animate-spin" />}
                            </div>
                        </CardContent>
                    </Card>

                    {/* 说明 */}
                    <Card className="border-border/70 bg-card lg:col-span-2">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Database className="h-4 w-4" />
                                说明
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2 text-sm text-muted-foreground">
                            <p>
                                配置写入仓库根 <code className="font-mono text-xs">.env</code>，修改后需重启后端 + Worker 进程生效。
                            </p>
                            <p>
                                「抖音登录模式」决定扫码/登录时使用的实现：
                                <span className="text-foreground"> 浏览器 </span>
                                = DouyinAdapter（Patchright 浏览器登录），
                                <span className="text-foreground"> 逆向 HTTP </span>
                                = DouyinHttpAdapter（逆向 HTTP API，测试）。
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    )
}
