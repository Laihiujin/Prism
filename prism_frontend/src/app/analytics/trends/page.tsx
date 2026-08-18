"use client"

import { useMemo, useState, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { Play, Heart, MessageCircle, Bookmark, Calendar, TrendingUp } from "lucide-react"

import { PageHeader } from "@/components/layout/page-scaffold"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AnalyticsChart } from "../components/analytics-chart"
import { StatsCard } from "../components/stats-card"
import { AnalyticsSummary, VideoAnalytics } from "../types"

const METRICS = {
    play: { label: "播放量", key: "playCount", color: "#3b82f6", icon: <Play className="h-4 w-4" /> },
    like: { label: "点赞", key: "likeCount", color: "#ec4899", icon: <Heart className="h-4 w-4" /> },
    comment: { label: "评论", key: "commentCount", color: "#06b6d4", icon: <MessageCircle className="h-4 w-4" /> },
    collect: { label: "收藏", key: "collectCount", color: "#22c55e", icon: <Bookmark className="h-4 w-4" /> },
}

export default function TrendsPage() {
    const [chartMetric, setChartMetric] = useState<keyof typeof METRICS>("play")

    const accountIdOf = useCallback((account: any) => {
        const result = String(account?.id ?? "").trim()
        return result
    }, [])

    const { data: accountsData } = useQuery({
        queryKey: ["accounts"],
        queryFn: async () => {
            const res = await fetch("/api/accounts?limit=1000")
            if (!res.ok) throw new Error("Failed to fetch accounts")
            return res.json()
        },
        refetchInterval: 10000,
    })

    const accounts = useMemo(() => {
        if (Array.isArray(accountsData)) return accountsData
        if (Array.isArray((accountsData as any)?.data)) return (accountsData as any).data
        return []
    }, [accountsData])

    const accountIds = useMemo(() => {
        return accounts.map(accountIdOf).filter(Boolean)
    }, [accounts, accountIdOf])

    const { data: analyticsData, isLoading } = useQuery({
        queryKey: ["analytics-trends", accountIds],
        queryFn: async () => {
            const params = new URLSearchParams()
            accountIds.forEach((id) => params.append("accounts", id))
            const res = await fetch(`/api/analytics?${params}`)
            if (!res.ok) throw new Error("Failed to fetch analytics")
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

    const topVideos = useMemo(() => {
        return [...videos]
            .sort((a, b) => (b.playCount || 0) - (a.playCount || 0))
            .slice(0, 6)
    }, [videos])

    const formatNumber = (num: number) => {
        if (num >= 10000) {
            return (num / 10000).toFixed(1) + "万"
        }
        return num.toLocaleString()
    }

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
            <PageHeader
                title="数据趋势"
                description="全账号实时指标概览。"
            />

            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <StatsCard
                    title="总播放量"
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
                    title="收藏"
                    value={formatNumber(summary.totalCollects)}
                    icon={<Bookmark className="h-4 w-4" />}
                    color="green"
                    onClick={() => setChartMetric("collect")}
                    isActive={chartMetric === "collect"}
                />
                <StatsCard
                    title="视频数"
                    value={summary.totalVideos.toString()}
                    icon={<Calendar className="h-4 w-4" />}
                    color="orange"
                />
            </div>

            <Card className="border-white/10 bg-black/40">
                <CardHeader>
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <CardTitle>{METRICS[chartMetric].label}趋势</CardTitle>
                            <CardDescription>每日表现变化。</CardDescription>
                        </div>
                        <div className="flex items-center bg-black/40 rounded-lg p-1 border border-white/10">
                            {Object.entries(METRICS).map(([key, config]) => (
                                <button
                                    key={key}
                                    onClick={() => setChartMetric(key as keyof typeof METRICS)}
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
                        dataKey={METRICS[chartMetric].key}
                        color={METRICS[chartMetric].color}
                        title={METRICS[chartMetric].label}
                    />
                </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-2">
                <Card className="border-white/10 bg-black/40">
                    <CardHeader>
                        <div className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-primary" />
                            <CardTitle>热门视频</CardTitle>
                        </div>
                        <CardDescription>按播放量排序。</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isLoading ? (
                            <div className="text-sm text-white/50">加载中...</div>
                        ) : topVideos.length === 0 ? (
                            <div className="text-sm text-white/50">暂无分析数据。</div>
                        ) : (
                            <div className="space-y-3">
                                {topVideos.map((video) => (
                                    <div key={video.id} className="flex items-center justify-between gap-3">
                                        <div className="min-w-0">
                                            <div className="text-sm text-white truncate">{video.title || "未命名"}</div>
                                            <div className="text-xs text-white/50">{video.platform}</div>
                                        </div>
                                        <Badge className="bg-white/10 text-white border-white/10">
                                            {formatNumber(video.playCount || 0)}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="border-white/10 bg-black/40">
                    <CardHeader>
                        <CardTitle>表现汇总</CardTitle>
                        <CardDescription>近期活动概览。</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 gap-4">
                            {Object.entries(METRICS).map(([key, metric]) => (
                                <div key={key} className="rounded-lg border border-white/10 bg-black/30 p-4">
                                    <div className="flex items-center justify-between text-xs text-white/60 mb-2">
                                        <span>{metric.label}</span>
                                        {metric.icon}
                                    </div>
                                    <div className="text-xl font-semibold text-white">
                                        {formatNumber(
                                            key === "play"
                                                ? summary.totalPlays
                                                : key === "like"
                                                    ? summary.totalLikes
                                                    : key === "comment"
                                                        ? summary.totalComments
                                                        : summary.totalCollects
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
