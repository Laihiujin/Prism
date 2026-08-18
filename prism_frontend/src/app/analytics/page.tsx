"use client"
import { PageHeader } from "@/components/layout/page-scaffold"

import { useEffect, useMemo, useState, useRef, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Calendar, Download, Play, Heart, MessageCircle, Bookmark, X, Check, Search, Filter as FilterIcon } from "lucide-react"
import Image from "next/image"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { DatePicker } from "@/components/ui/date-picker"
import { VideoDataTable } from "./components/video-data-table"
import { VideoAnalytics, AnalyticsSummary } from "./types"
import { AnalyticsChart } from "./components/analytics-chart"
import { StatsCard } from "./components/stats-card"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

const PLATFORMS = [
    { value: "douyin", label: "抖音", icon: "/Tiktok.svg" },
    { value: "bilibili", label: "B站", icon: "/Bilibili.svg" },
]

const TIME_PRESETS = [
    { value: "all", label: "全部" },
    { value: "30d", label: "最近1个月" },
    { value: "60d", label: "最近2个月" },
    { value: "90d", label: "最近3个月" },
    { value: "720d", label: "最近2年" },
    { value: "custom", label: "自定义" }
]

export default function AnalyticsPage() {
    const { toast } = useToast()
    const [startDate, setStartDate] = useState<string>()
    const [endDate, setEndDate] = useState<string>()

    // 筛选状态
    const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
    const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
    const [timePreset, setTimePreset] = useState<string>("all")

    // 侧边栏状态
    const [accountDrawerOpen, setAccountDrawerOpen] = useState(false)
    const [accountSearchKeyword, setAccountSearchKeyword] = useState("")
    const [accountDrawerPage, setAccountDrawerPage] = useState(1)
    const accountDrawerPerPage = 20

    // Chart Metric Selection
    const [chartMetric, setChartMetric] = useState<"play" | "like" | "comment" | "collect">("play")

    const metricConfig = {
        play: { label: "播放量", key: "playCount", color: "#3b82f6" },
        like: { label: "点赞", key: "likeCount", color: "#ec4899" },
        comment: { label: "评论", key: "commentCount", color: "#06b6d4" },
        collect: { label: "收藏", key: "collectCount", color: "#22c55e" }
    }

    // 获取账号列表
    const { data: accountsData } = useQuery({
        queryKey: ['accounts'],
        queryFn: async () => {
            const res = await fetch('/api/accounts?limit=1000')
            if (!res.ok) throw new Error('Failed to fetch accounts')
            return res.json()
        },
        refetchInterval: 10000,
    })

    const accounts = useMemo(() => {
        if (Array.isArray(accountsData)) return accountsData
        if (Array.isArray((accountsData as any)?.data)) return (accountsData as any).data
        return []
    }, [accountsData])

    const accountIdOf = useCallback((account: any) => {
        // Backend returns 'id' field (e.g., "account_1767686579461")
        const result = String(account?.id ?? "").trim()
        return result
    }, [])

    // Initialize default selection
    const initializedRef = useRef(false)

    useEffect(() => {
        if (accounts.length === 0 || initializedRef.current) return
        const defaultPlatforms = PLATFORMS.map((platform) => platform.value)
        const defaultAccountIds = accounts
            .filter((account: any) => defaultPlatforms.includes(account.platform))
            .map(accountIdOf)
            .filter(Boolean)

        setSelectedPlatforms(defaultPlatforms)
        setSelectedAccounts(defaultAccountIds)
        initializedRef.current = true
    }, [accounts, accountIdOf])

    // Filter accounts based on selected platforms
    const filteredAccounts = useMemo(() => {
        // If no platform selected, show no accounts
        if (selectedPlatforms.length === 0) {
            return []
        }
        // Filter by selected platforms
        return accounts.filter((account: any) =>
            selectedPlatforms.includes(account.platform)
        )
    }, [accounts, selectedPlatforms])

    const accountIds = useMemo(
        () => filteredAccounts.map(accountIdOf).filter(Boolean),
        [filteredAccounts]
    )

    // Clean up selected accounts when platforms change
    useEffect(() => {
        if (selectedAccounts.length === 0) return

        const validAccountIds = new Set(accountIds)
        const cleanedAccounts = selectedAccounts.filter(id => validAccountIds.has(id))

        if (cleanedAccounts.length !== selectedAccounts.length) {
            setSelectedAccounts(cleanedAccounts)
        }
    }, [accountIds, selectedAccounts])

    // Get account display name
    const getAccountDisplayName = useCallback((account: any) => {
        return (account.original_name && account.original_name.trim()) ||
            (account.name && !account.name.startsWith("account_") ? account.name : null) ||
            account.user_id ||
            account.account_id
    }, [])

    // 根据时间预设自动计算日期
    const getDateRangeFromPreset = (preset: string) => {
        if (preset === "custom") return { start: startDate, end: endDate }
        if (preset === "all") return { start: undefined, end: undefined }

        const today = new Date()
        const end = today.toISOString().split('T')[0]
        let start = new Date()

        switch (preset) {
            case "30d":
                start.setDate(today.getDate() - 30)
                break
            case "60d":
                start.setDate(today.getDate() - 60)
                break
            case "90d":
                start.setDate(today.getDate() - 90)
                break
            case "720d":
                start.setDate(today.getDate() - 720)
                break
        }

        return { start: start.toISOString().split('T')[0], end }
    }

    const dateRange = timePreset === "custom" ? { start: startDate, end: endDate } : getDateRangeFromPreset(timePreset)

    // Fetch analytics data with filters
    const { data: analyticsData, isLoading, refetch } = useQuery({
        queryKey: ['analytics', dateRange.start, dateRange.end, selectedPlatforms, selectedAccounts],
        queryFn: async () => {
            if (selectedAccounts.length === 0) {
                return {
                    code: 200, summary: {
                        totalVideos: 0,
                        totalPlays: 0,
                        totalLikes: 0,
                        totalComments: 0,
                        totalCollects: 0,
                        avgPlayCount: 0,
                    }, videos: [], chartData: []
                }
            }

            const params = new URLSearchParams()
            if (dateRange.start) params.append('startDate', dateRange.start)
            if (dateRange.end) params.append('endDate', dateRange.end)

            if (selectedPlatforms.length > 0 && selectedPlatforms.length < PLATFORMS.length) {
                selectedPlatforms.forEach(p => params.append('platforms', p))
            }
            if (selectedAccounts.length > 0) {
                selectedAccounts.forEach(a => params.append('accounts', a))
            }

            const res = await fetch(`/api/analytics?${params}`)
            if (!res.ok) throw new Error('Failed to fetch analytics')
            return res.json()
        },
    })

    const summary: AnalyticsSummary = analyticsData?.summary || {
        totalVideos: 0,
        totalPlays: 0,
        totalLikes: 0,
        totalComments: 0,
        totalCollects: 0,
        avgPlayCount: 0,
    }

    const videos: VideoAnalytics[] = analyticsData?.videos || []
    const chartData = analyticsData?.chartData || []

    const handleExport = async (format: 'csv' | 'excel') => {
        try {
            const params = new URLSearchParams()
            if (dateRange.start) params.append('startDate', dateRange.start)
            if (dateRange.end) params.append('endDate', dateRange.end)
            params.append('format', format)

            if (selectedPlatforms.length > 0 && selectedPlatforms.length < PLATFORMS.length) {
                selectedPlatforms.forEach(p => params.append('platforms', p))
            }
            if (selectedAccounts.length > 0) {
                selectedAccounts.forEach(a => params.append('accounts', a))
            }

            const res = await fetch(`/api/analytics/export?${params}`)
            if (!res.ok) throw new Error('Export failed')

            const blob = await res.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `analytics_${Date.now()}.${format === 'csv' ? 'csv' : 'xlsx'}`
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)

            toast({ title: `数据已导出为 ${format.toUpperCase()}` })
        } catch (error) {
            toast({ variant: "destructive", title: "导出失败", description: String(error) })
        }
    }

    const formatNumber = (num: number) => {
        if (num >= 10000) {
            return (num / 10000).toFixed(1) + 'w'
        }
        return num.toLocaleString()
    }

    // Toggle platform selection
    const togglePlatform = (platform: string) => {
        setSelectedPlatforms(prev =>
            prev.includes(platform)
                ? prev.filter(p => p !== platform)
                : [...prev, platform]
        )
    }

    // Toggle account selection
    const toggleAccount = (accountId: string) => {
        setSelectedAccounts(prev => {
            const isCurrentlySelected = prev.includes(accountId)
            return isCurrentlySelected
                ? prev.filter(id => id !== accountId)
                : [...prev, accountId]
        })
    }

    // Filter and paginate accounts in drawer
    const drawerFilteredAccounts = useMemo(() => {
        if (!accountSearchKeyword.trim()) return filteredAccounts
        const keyword = accountSearchKeyword.toLowerCase()
        return filteredAccounts.filter((acc: any) => {
            const displayName = getAccountDisplayName(acc).toLowerCase()
            const userId = (acc.user_id || "").toLowerCase()
            return displayName.includes(keyword) || userId.includes(keyword)
        })
    }, [filteredAccounts, accountSearchKeyword, getAccountDisplayName])

    const drawerPaginatedAccounts = useMemo(() => {
        const startIndex = (accountDrawerPage - 1) * accountDrawerPerPage
        return drawerFilteredAccounts.slice(startIndex, startIndex + accountDrawerPerPage)
    }, [drawerFilteredAccounts, accountDrawerPage])

    const totalDrawerPages = Math.ceil(drawerFilteredAccounts.length / accountDrawerPerPage)

    const selectedAccountsList = useMemo(() => {
        return accounts.filter((acc: any) => selectedAccounts.includes(accountIdOf(acc)))
    }, [accounts, selectedAccounts])

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="数据中心"
                actions={
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-9 border-white/10 bg-white/5 hover:bg-white/10"
                            onClick={() => setAccountDrawerOpen(true)}
                        >
                            <FilterIcon className="mr-2 h-4 w-4" />
                            筛选账号
                            {selectedAccounts.length > 0 && (
                                <Badge className="ml-2 bg-primary/20 text-primary border-primary/30">
                                    {selectedAccounts.length}
                                </Badge>
                            )}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-9 border-white/10 bg-white/5 hover:bg-white/10"
                            onClick={() => handleExport('csv')}
                        >
                            <Download className="mr-2 h-4 w-4" />
                            导出CSV
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-9 border-white/10 bg-white/5 hover:bg-white/10"
                            onClick={() => handleExport('excel')}
                        >
                            <Download className="mr-2 h-4 w-4" />
                            导出Excel
                        </Button>
                    </div>
                }
            />

            {/* Time Range Filter */}
            <div className="flex flex-col gap-4 p-5 rounded-2xl border border-white/10 bg-black/40 backdrop-blur-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    <Label className="text-sm text-white/60 font-medium shrink-0">时间范围</Label>
                    <div className="flex flex-wrap items-center gap-2 bg-black/20 p-1.5 rounded-xl border border-white/5 w-full sm:w-auto">
                        {TIME_PRESETS.map(preset => (
                            <button
                                key={preset.value}
                                onClick={() => {
                                    setTimePreset(preset.value)
                                    if (preset.value !== 'custom') {
                                        setStartDate(undefined)
                                        setEndDate(undefined)
                                    }
                                }}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${timePreset === preset.value
                                    ? "bg-primary/20 text-primary border border-primary/30"
                                    : "text-white/50 hover:text-white hover:bg-white/5"
                                    }`}
                            >
                                {preset.label}
                            </button>
                        ))}
                    </div>
                </div>

                {timePreset === "custom" && (
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 animate-in fade-in">
                        <Label className="text-sm text-white/60 font-medium shrink-0">自定义日期</Label>
                        <div className="flex items-center gap-3">
                            <DatePicker
                                value={startDate}
                                onChange={setStartDate}
                                placeholder="开始日期"
                                className="w-40 h-10 text-sm"
                            />
                            <span className="text-white/30">至</span>
                            <DatePicker
                                value={endDate}
                                onChange={setEndDate}
                                placeholder="结束日期"
                                className="w-40 h-10 text-sm"
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Empty State or Data */}
            {selectedAccounts.length === 0 ? (
                <Card className="border-white/10 bg-black/40">
                    <CardContent className="py-16">
                        <div className="text-center space-y-4">
                            <div className="w-20 h-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                                <FilterIcon className="w-10 h-10 text-primary/50" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-white/80 mb-2">请选择账号查看数据</h3>
                                <p className="text-sm text-white/50 mb-4">
                                    点击右上角"筛选账号"按钮选择要分析的账号
                                </p>
                                <Button
                                    variant="outline"
                                    onClick={() => setAccountDrawerOpen(true)}
                                    className="border-primary/30 text-primary hover:bg-primary/10"
                                >
                                    <FilterIcon className="mr-2 h-4 w-4" />
                                    选择账号
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* Statistics Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                        <StatsCard
                            title="播放总量"
                            value={formatNumber(summary.totalPlays)}
                            icon={<Play className="h-4 w-4" />}
                            color="blue"
                            onClick={() => setChartMetric("play")}
                            isActive={chartMetric === "play"}
                        />
                        <StatsCard
                            title="点赞"
                            value={formatNumber(summary.totalLikes)}
                            icon={<Heart className="h-4 w-4" />}
                            color="pink"
                            onClick={() => setChartMetric("like")}
                            isActive={chartMetric === "like"}
                        />
                        <StatsCard
                            title="评论"
                            value={formatNumber(summary.totalComments)}
                            icon={<MessageCircle className="h-4 w-4" />}
                            color="cyan"
                            onClick={() => setChartMetric("comment")}
                            isActive={chartMetric === "comment"}
                        />
                        <StatsCard
                            title="收藏/分享"
                            value={formatNumber(summary.totalCollects)}
                            icon={<Bookmark className="h-4 w-4" />}
                            color="green"
                            onClick={() => setChartMetric("collect")}
                            isActive={chartMetric === "collect"}
                        />
                        <StatsCard
                            title="视频总数"
                            value={summary.totalVideos.toString()}
                            icon={<Calendar className="h-4 w-4" />}
                            color="orange"
                        />
                    </div>

                    {/* Trend Chart */}
                    <Card className="border-white/10 bg-black/40">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle>{metricConfig[chartMetric].label}趋势</CardTitle>
                                    <CardDescription>近期{metricConfig[chartMetric].label}数据变化</CardDescription>
                                </div>
                                <div className="flex items-center bg-black/40 rounded-lg p-1 border border-white/10">
                                    {Object.entries(metricConfig).map(([key, config]) => (
                                        <button
                                            key={key}
                                            onClick={() => setChartMetric(key as any)}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${chartMetric === key ? "bg-white/10 text-white shadow-sm" : "text-white/40 hover:text-white/80"}`}
                                        >
                                            {config.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <AnalyticsChart
                                data={chartData}
                                dataKey={metricConfig[chartMetric].key}
                                color={metricConfig[chartMetric].color}
                                title={metricConfig[chartMetric].label}
                            />
                        </CardContent>
                    </Card>

                    {/* Video Data Table */}
                    <Card className="border-white/10 bg-black/40">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle>视频数据明细</CardTitle>
                                    <CardDescription>所有视频的详细数据统计</CardDescription>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <VideoDataTable data={videos} isLoading={isLoading} />
                        </CardContent>
                    </Card>
                </>
            )}

            {/* Account Selection Drawer */}
            <Sheet open={accountDrawerOpen} onOpenChange={setAccountDrawerOpen}>
                <SheetContent
                    side="right"
                    className="w-[95vw] sm:w-[90vw] lg:w-[75vw] xl:w-[700px] sm:max-w-none bg-neutral-900 border-white/10 text-white overflow-w-auto"
                >
                    <SheetHeader>
                        <SheetTitle className="text-white">选择账号</SheetTitle>
                        <SheetDescription className="text-white/60">
                            {selectedPlatforms.length === 0
                                ? "请先选择平台"
                                : `从 ${filteredAccounts.length} 个可用账号中选择`}
                        </SheetDescription>
                    </SheetHeader>

                    <div className="mt-6 space-y-4">
                        {/* Platform Filter */}
                        <div className="space-y-3">
                            <Label className="text-sm text-white/70">平台筛选</Label>
                            <div className="flex flex-wrap gap-2">
                                {PLATFORMS.map(platform => {
                                    const isSelected = selectedPlatforms.includes(platform.value)
                                    return (
                                        <button
                                            key={platform.value}
                                            onClick={() => togglePlatform(platform.value)}
                                            className={cn(
                                                "flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm font-medium",
                                                isSelected
                                                    ? "bg-primary/15 border-primary/40 text-white"
                                                    : "bg-black/30 border-white/10 text-white/50 hover:bg-white/5"
                                            )}
                                        >
                                            <Image
                                                src={platform.icon}
                                                alt={platform.label}
                                                width={16}
                                                height={16}
                                                className="object-contain"
                                            />
                                            {platform.label}
                                        </button>
                                    )
                                })}
                            </div>
                        </div>

                        {/* Search */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                            <Input
                                placeholder="搜索账号名称或ID..."
                                className="pl-9 bg-black/20 border-white/10"
                                value={accountSearchKeyword}
                                onChange={(e) => {
                                    setAccountSearchKeyword(e.target.value)
                                    setAccountDrawerPage(1)
                                }}
                            />
                        </div>

                        {/* Selected Count and Actions */}
                        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-primary/10 border border-primary/20">
                            <div className="text-sm text-white/80">
                                已选择 <span className="font-semibold text-primary">{selectedAccounts.length}</span> / {drawerFilteredAccounts.length} 个账号
                            </div>
                            <div className="flex items-center gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 text-xs text-primary hover:text-primary/80 hover:bg-primary/10"
                                    onClick={() => {
                                        const allIds = drawerFilteredAccounts.map((acc: any) => accountIdOf(acc))
                                        setSelectedAccounts(allIds)
                                    }}
                                >
                                    全选
                                </Button>
                                {selectedAccounts.length > 0 && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                        onClick={() => setSelectedAccounts([])}
                                    >
                                        取消全选
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Account Table */}
                        <div className="border border-white/10 rounded-lg overflow-hidden">
                            <div className="bg-black/40">
                                <div className="grid grid-cols-[40px_60px_1fr_150px_100px_60px] gap-3 px-4 py-3 text-xs font-medium text-white/60 border-b border-white/10">
                                    <div className="text-center">#</div>
                                    <div>头像</div>
                                    <div>账号名称</div>
                                    <div>账号ID</div>
                                    <div>平台</div>
                                    <div className="text-center">选择</div>
                                </div>
                            </div>

                            {drawerPaginatedAccounts.length > 0 ? (
                                <div className="divide-y divide-white/10">
                                    {drawerPaginatedAccounts.map((account: any, index: number) => {
                                        const accountId = accountIdOf(account)
                                        const isSelected = selectedAccounts.includes(accountId)
                                        const displayName = getAccountDisplayName(account)
                                        const globalIndex = (accountDrawerPage - 1) * accountDrawerPerPage + index + 1

                                        return (
                                            <div
                                                key={accountId}
                                                className={cn(
                                                    "grid grid-cols-[40px_60px_1fr_150px_100px_60px] gap-3 px-4 py-3 items-center hover:bg-white/5 transition-colors cursor-pointer",
                                                    isSelected && "bg-primary/10"
                                                )}
                                                onClick={() => toggleAccount(accountId)}
                                            >
                                                <div className="text-center text-xs text-white/40">{globalIndex}</div>
                                                <div className="relative w-10 h-10">
                                                    <div className="w-10 h-10 rounded-full bg-neutral-800 flex items-center justify-center border border-white/10 overflow-hidden">
                                                        {account.avatar ? (
                                                            <img
                                                                src={account.avatar}
                                                                alt={displayName}
                                                                className="object-cover w-full h-full"
                                                                referrerPolicy="no-referrer"
                                                            />
                                                        ) : (
                                                            <span className="text-sm font-medium">{displayName.slice(0, 1)}</span>
                                                        )}
                                                    </div>
                                                    <div className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-neutral-900 border border-white/10 flex items-center justify-center p-0.5">
                                                        <Image
                                                            src={PLATFORMS.find(p => p.value === account.platform)?.icon ?? "/Tiktok.svg"}
                                                            alt={account.platform}
                                                            width={12}
                                                            height={12}
                                                            className="object-contain"
                                                        />
                                                    </div>
                                                </div>
                                                <div className={cn("text-sm font-medium truncate", isSelected ? "text-primary" : "text-white")}>
                                                    {displayName}
                                                </div>
                                                <div className="text-xs truncate text-white/50">{account.user_id || "未知"}</div>
                                                <div className="text-xs truncate text-white/60">
                                                    {PLATFORMS.find(p => p.value === account.platform)?.label || account.platform}
                                                </div>
                                                <div className="flex justify-center">
                                                    <div
                                                        className={cn(
                                                            "w-5 h-5 rounded border flex items-center justify-center transition-all",
                                                            isSelected ? "bg-primary border-primary" : "border-white/30 hover:border-white/50"
                                                        )}
                                                    >
                                                        {isSelected && <Check className="w-3 h-3 text-black" />}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            ) : (
                                <div className="py-12 text-center text-white/40 text-sm">
                                    {selectedPlatforms.length === 0
                                        ? "请先在上方选择平台"
                                        : accountSearchKeyword
                                            ? "没有找到匹配的账号"
                                            : "暂无可用账号"}
                                </div>
                            )}
                        </div>

                        {/* Pagination */}
                        {totalDrawerPages > 1 && (
                            <div className="flex items-center justify-between pt-2">
                                <div className="text-xs text-white/50">
                                    显示 {(accountDrawerPage - 1) * accountDrawerPerPage + 1} - {Math.min(accountDrawerPage * accountDrawerPerPage, drawerFilteredAccounts.length)} / 共 {drawerFilteredAccounts.length} 个账号
                                </div>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setAccountDrawerPage(p => Math.max(1, p - 1))}
                                        disabled={accountDrawerPage === 1}
                                        className="h-7 text-xs border-white/10 bg-white/5"
                                    >
                                        上一页
                                    </Button>
                                    <div className="text-xs text-white/60">{accountDrawerPage} / {totalDrawerPages}</div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setAccountDrawerPage(p => Math.min(totalDrawerPages, p + 1))}
                                        disabled={accountDrawerPage === totalDrawerPages}
                                        className="h-7 text-xs border-white/10 bg-white/5"
                                    >
                                        下一页
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Footer Actions */}
                        <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
                            <Button
                                variant="ghost"
                                onClick={() => setAccountDrawerOpen(false)}
                            >
                                取消
                            </Button>
                            <Button
                                onClick={() => setAccountDrawerOpen(false)}
                                className="bg-primary text-black"
                            >
                                确定 ({selectedAccounts.length})
                            </Button>
                        </div>
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    )
}
