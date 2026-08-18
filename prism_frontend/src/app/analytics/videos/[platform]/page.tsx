"use client"

import { useEffect, useState, useMemo, Fragment } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import {
    Video,
    RefreshCw,
    TrendingUp,
    Eye,
    Heart,
    MessageCircle,
    Share2,
    Loader2,
    Calendar,
    BarChart3,
    ArrowUpRight,
    Users,
    Zap,
    Bookmark,
    MessageSquare,
    Coins,
    Star,
    Send
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useToast } from "@/components/ui/use-toast"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from "@/components/ui/select"
import { PageHeader } from "@/components/layout/page-scaffold"
import { cn } from "@/lib/utils"

const PLATFORMS_CONFIG: Record<string, {
    label: string
    color: string
    stats: { label: string; key: string; icon: any; color: string }[]
    metrics: string[]
}> = {
    douyin: {
        label: "抖音",
        color: "from-neutral-900 to-neutral-990",
        stats: [
            { label: "总播放", key: "views", icon: Eye, color: "text-blue-400" },
            { label: "总点赞", key: "likes", icon: Heart, color: "text-pink-400" },
            { label: "总评论", key: "comments", icon: MessageCircle, color: "text-cyan-400" },
            { label: "总收藏", key: "collects", icon: Bookmark, color: "text-amber-400" },
            { label: "总分享", key: "shares", icon: Share2, color: "text-green-400" },
            // { label: "总粉丝数", key: "follower", icon: Users, color: "text-white-400" },
        ],
        metrics: ["views", "likes", "comments", "shares", "collects"]
    },
    bilibili: {
        label: "B站",
        color: "from-neutral-900 to-neutral-990",
        stats: [
            // { label: "总粉丝数", key: "follower", icon: Users, color: "text-black-400" },
            { label: "总播放", key: "views", icon: Eye, color: "text-blue-400" },
            { label: "总点赞", key: "likes", icon: Heart, color: "text-red-400" },
            { label: "总评论", key: "comments", icon: MessageCircle, color: "text-purple-400" },
            { label: "总收藏", key: "collects", icon: Star, color: "text-orange-400" },
            { label: "总分享", key: "shares", icon: Share2, color: "text-green-400" },
            { label: "总硬币", key: "coins", icon: Coins, color: "text-yellow-400" },
            { label: "总弹幕", key: "danmaku", icon: MessageSquare, color: "text-red-400" },


        ],
        metrics: ["views", "likes", "coins", "collects", "danmaku"]
    },
    kuaishou: {
        label: "快手",
        color: "from-neutral-900 to-neutral-990",
        stats: [
            { label: "总播放", key: "views", icon: Eye, color: "text-blue-400" },
            { label: "总点赞", key: "likes", icon: Heart, color: "text-red-400" },
            { label: "总评论", key: "comments", icon: MessageCircle, color: "text-orange-400" },
            { label: "互动率", key: "engagement", icon: Zap, color: "text-yellow-400" },
        ],
        metrics: ["views", "likes", "comments", "shares"]
    },
    xiaohongshu: {
        label: "小红书",
        color: "from-neutral-900 to-neutral-990",
        stats: [
            { label: "总点赞", key: "likes", icon: Heart, color: "text-red-400" },
            { label: "总收藏", key: "collects", icon: Bookmark, color: "text-amber-400" },
            { label: "总评论", key: "comments", icon: MessageCircle, color: "text-pink-400" },
            { label: "粉丝转化", key: "conversion", icon: Users, color: "text-red-400" },
        ],
        metrics: ["likes", "collects", "comments", "shares"]
    },
    channels: {
        label: "视频号",
        color: "from-neutral-900 to-neutral-990",
        stats: [
            { label: "总播放", key: "views", icon: Eye, color: "text-blue-400" },
            { label: "总点赞", key: "likes", icon: Heart, color: "text-red-400" },
            { label: "总转发", key: "shares", icon: Send, color: "text-emerald-400" },
            { label: "总评论", key: "comments", icon: MessageCircle, color: "text-teal-400" },
        ],
        metrics: ["views", "likes", "comments", "shares", "collects"]
    }
}

export default function PlatformVideosPage() {
    const params = useParams()
    const platform = (params.platform as string) || "douyin"
    const config = PLATFORMS_CONFIG[platform] || PLATFORMS_CONFIG.douyin

    const { toast } = useToast()
    const queryClient = useQueryClient()
    const [isCollecting, setIsCollecting] = useState(false)
    const [isSheetOpen, setIsSheetOpen] = useState(false)
    const [sheetPage, setSheetPage] = useState(1)
    const [sheetPageSize, setSheetPageSize] = useState(20)
    const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})

    // 热门视频分页状态
    const [hotVideosPage, setHotVideosPage] = useState(1)
    const hotVideosPerPage = 20

    // Fetch video data for specific platform
    const { data: videosData, isLoading, refetch } = useQuery({
        queryKey: ["videos", platform],
        queryFn: async () => {
            const params = new URLSearchParams()
            params.append("platform", platform)
            params.append("limit", "50")

            const res = await fetch(`/api/analytics/videos?${params}`)
            if (!res.ok) throw new Error("Failed to fetch videos")
            return res.json()
        },
        refetchInterval: 30000,
    })

    const rawVideos = videosData?.data || []
    const summary = videosData?.summary || null

    const normalizeCoverUrl = (raw: any) => {
        const url = String(raw || "").trim()
        if (!url) return ""
        if (url.startsWith("//")) return `https:${url}`
        if (url.startsWith("http://")) return `https://${url.slice(7)}`
        return url
    }

    const parseRawData = (value: any) => {
        if (!value) return null
        if (typeof value === "object") return value
        if (typeof value !== "string") return null
        try {
            return JSON.parse(value)
        } catch {
            return null
        }
    }

    const normalizeVideo = (video: any) => ({
        ...video,
        views: video.views || video.playCount || video.play_count || 0,
        likes: video.likes || video.likeCount || video.like_count || 0,
        comments: video.comments || video.commentCount || video.comment_count || 0,
        shares: video.shares || video.shareCount || video.share_count || 0,
        collects: video.collects || video.collectCount || video.collect_count || video.favorites || 0,
        coins: video.coins || 0,
        danmaku: video.danmaku || 0,
        publish_time: video.publish_time || video.publishTime || video.publishDate || video.publish_date || "",
        cover_url: normalizeCoverUrl(
            video.cover_url || video.coverUrl || video.thumbnail || video.pic || video.cover || ""
        ),
        video_url: video.video_url || video.videoUrl || "",
        duration: video.duration || 0,
        author_name: video.author_name || video.accountName || video.account_name || video.author || "",
        author_avatar: video.author_avatar || video.accountAvatar || video.account_avatar || "",
        video_id: video.videoId || video.video_id || video.videoId || "",
        account_id: video.accountId || video.account_id || "",
        account_name: video.accountName || video.account_name || "",
        platform: video.platform || platform,
        status: video.status || "",
        collected_at: video.collectedAt || video.collected_at || "",
        raw_data: parseRawData(video.raw_data || video.rawData || video.rawData || video.raw_data),
    })

    const videos = useMemo(() => rawVideos.map(normalizeVideo), [rawVideos])

    const summaryStats = useMemo(() => {
        if (!summary) {
            return null
        }
        const views = summary.totalPlays || 0
        const likes = summary.totalLikes || 0
        const comments = summary.totalComments || 0
        const collects = summary.totalCollects || 0
        const shares = summary.totalShares || 0
        const engagement = views > 0 ? Number(((likes + comments + shares) / views * 100).toFixed(2)) : 0
        return {
            views,
            likes,
            comments,
            shares,
            collects,
            coins: 0,
            danmaku: 0,
            engagement
        }
    }, [summary])

    // Calculate aggregate stats
    const statsFromVideos = useMemo(() => {
        const total = {
            views: 0,
            likes: 0,
            comments: 0,
            shares: 0,
            collects: 0,
            coins: 0,
            danmaku: 0,
            engagement: 0
        }

        videos.forEach((v: any) => {
            total.views += (v.views || 0)
            total.likes += (v.likes || 0)
            total.comments += (v.comments || 0)
            total.shares += (v.shares || 0)
            total.collects += (v.collects || 0)
            total.coins += (v.coins || 0)
            total.danmaku += (v.danmaku || 0)
        })

        if (total.views > 0) {
            total.engagement = Number(((total.likes + total.comments + total.shares) / total.views * 100).toFixed(2))
        }

        return total
    }, [videos])

    const stats = useMemo(() => {
        if (videos.length > 0) {
            return statsFromVideos
        }
        if (summaryStats) {
            return summaryStats
        }
        return statsFromVideos
    }, [summaryStats, statsFromVideos, videos.length])

    // 多维度评分算法 - 综合考虑播放、点赞、评论、收藏、分享
    const calculateVideoScore = (video: any) => {
        const weights = {
            views: 0.3,      // 播放量权重30%
            likes: 0.25,     // 点赞权重25%
            comments: 0.2,   // 评论权重20%
            collects: 0.15,  // 收藏权重15%
            shares: 0.1      // 分享权重10%
        }

        // 归一化处理：获取各项最大值
        const maxViews = Math.max(...videos.map((v: any) => v.views || 0), 1)
        const maxLikes = Math.max(...videos.map((v: any) => v.likes || 0), 1)
        const maxComments = Math.max(...videos.map((v: any) => v.comments || 0), 1)
        const maxCollects = Math.max(...videos.map((v: any) => v.collects || 0), 1)
        const maxShares = Math.max(...videos.map((v: any) => v.shares || 0), 1)

        // 计算归一化分数
        const normalizedViews = (video.views || 0) / maxViews
        const normalizedLikes = (video.likes || 0) / maxLikes
        const normalizedComments = (video.comments || 0) / maxComments
        const normalizedCollects = (video.collects || 0) / maxCollects
        const normalizedShares = (video.shares || 0) / maxShares

        // 加权求和
        const score =
            normalizedViews * weights.views +
            normalizedLikes * weights.likes +
            normalizedComments * weights.comments +
            normalizedCollects * weights.collects +
            normalizedShares * weights.shares

        return score
    }

    const sortedVideos = useMemo(() => {
        return [...videos].sort((a: any, b: any) => {
            const scoreA = calculateVideoScore(a)
            const scoreB = calculateVideoScore(b)
            return scoreB - scoreA
        })
    }, [videos])

    const sheetTotalPages = Math.max(1, Math.ceil(sortedVideos.length / sheetPageSize))
    const sheetVideos = useMemo(() => {
        const start = (sheetPage - 1) * sheetPageSize
        return sortedVideos.slice(start, start + sheetPageSize)
    }, [sortedVideos, sheetPage, sheetPageSize])

    // 热门视频分页逻辑 - 动态左右分配
    const hotVideosTotalPages = Math.max(1, Math.ceil(sortedVideos.length / hotVideosPerPage))
    const hotVideosData = useMemo(() => {
        const start = (hotVideosPage - 1) * hotVideosPerPage
        const pageVideos = sortedVideos.slice(start, start + hotVideosPerPage)

        // 动态分配到左右两栏
        const leftColumn: any[] = []
        const rightColumn: any[] = []

        pageVideos.forEach((video, index) => {
            if (index % 2 === 0) {
                leftColumn.push(video)
            } else {
                rightColumn.push(video)
            }
        })

        return { leftColumn, rightColumn }
    }, [sortedVideos, hotVideosPage, hotVideosPerPage])

    useEffect(() => {
        setSheetPage(1)
    }, [platform, sheetPageSize, sortedVideos.length])

    const videoCount = videos.length || summary?.totalVideos || 0

    const handleCollect = async () => {
        setIsCollecting(true)
        try {
            const res = await fetch(`/api/analytics/collect/${platform}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: "accounts", platform }),
            })
            const data = await res.json()

            if (data.success || res.ok) {
                toast({
                    title: `${config.label} 数据采集完成`,
                    description: `已成功同步最新的视频表现数据`,
                })
                refetch()
            } else {
                throw new Error(data.error || "采集失败")
            }
        } catch (error) {
            toast({
                title: "采集出错",
                description: String(error),
                variant: "destructive",
            })
        } finally {
            setIsCollecting(false)
        }
    }

    const formatNumber = (num: number) => {
        if (num >= 10000) return (num / 10000).toFixed(1) + "万"
        return num.toLocaleString()
    }

    const formatDuration = (value: number) => {
        if (!value) return "-"
        const totalSeconds = value > 1000 ? Math.round(value / 1000) : Math.round(value)
        const minutes = Math.floor(totalSeconds / 60)
        const seconds = totalSeconds % 60
        return `${minutes}:${String(seconds).padStart(2, "0")}`
    }

    const rowKey = (video: any, index: number) =>
        String(video.video_id || video.videoId || video.id || `${video.platform || "video"}-${index}`)

    const toggleRow = (key: string) => {
        setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }))
    }

    const formatValue = (value: any) => {
        if (value === null || value === undefined || value === "") return "-"
        if (typeof value === "number") return formatNumber(value)
        if (typeof value === "boolean") return value ? "true" : "false"
        if (typeof value === "object") return JSON.stringify(value)
        return String(value)
    }

    // 打开视频链接
    const handleOpenVideo = (video: any) => {
        const videoUrl = video.video_url || video.videoUrl
        if (videoUrl) {
            window.open(videoUrl, '_blank', 'noopener,noreferrer')
        } else {
            toast({
                title: "无法打开",
                description: "该视频没有可用的链接",
                variant: "destructive"
            })
        }
    }

    const extractExtraFields = (video: any) => {
        const raw = video.raw_data || {}
        if (!raw || typeof raw !== "object") return []

        if (video.platform === "bilibili") {
            return [
                { label: "BV号", value: raw.bvid || video.video_id },
                { label: "AV号", value: raw.aid },
                { label: "作者", value: raw.author },
                { label: "作者MID", value: raw.mid },
                { label: "分区ID", value: raw.typeid },
                { label: "时长", value: raw.length },
                { label: "简介", value: raw.description },
                { label: "弹幕", value: raw.video_review || raw.danmaku },
                { label: "硬币", value: raw.coins || raw.coin },
                { label: "收藏", value: raw.favorites },
                { label: "分享", value: raw.share },
            ].filter((item) => item.value !== undefined && item.value !== null && item.value !== "")
        }

        if (video.platform === "douyin") {
            const author = raw.author || {}
            const music = raw.music || {}
            const stats = raw.statistics || {}
            return [
                { label: "抖音号", value: author.unique_id || author.short_id || author.sec_uid },
                { label: "作者昵称", value: author.nickname },
                { label: "作者ID", value: author.uid },
                { label: "音乐", value: music.title },
                { label: "音乐作者", value: music.author },
                { label: "时长", value: raw.duration },
                { label: "分享链接", value: raw.share_url },
                { label: "播放", value: stats.play_count || stats.play_count_v2 },
                { label: "点赞", value: stats.digg_count },
                { label: "评论", value: stats.comment_count },
                { label: "收藏", value: stats.collect_count },
                { label: "分享", value: stats.share_count },
            ].filter((item) => item.value !== undefined && item.value !== null && item.value !== "")
        }

        return Object.keys(raw).slice(0, 12).map((key) => ({
            label: key,
            value: (raw as any)[key]
        }))
    }

    return (
        <div className="space-y-8 px-4 py-4 md:px-6 md:py-6 animate-in fade-in duration-500">
            <PageHeader
                title={`${config.label} 数据分析`}
                description={`针对 ${config.label} 平台的视频表现进行深度追踪与对比`}
                actions={
                    <div className="flex items-center gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setIsSheetOpen(true)}
                            className="border-black bg-black/40 text-white hover:bg-black/60 rounded-xl"
                        >
                            <BarChart3 className="mr-2 h-4 w-4" />
                            明细表格
                        </Button>
                        <Button
                            onClick={handleCollect}
                            disabled={isCollecting}
                            className={cn(
                                "bg-gradient-to-r text-white shadow-lg transition-all duration-300 hover:scale-105 rounded-xl",
                                config.color
                            )}
                        >
                            {isCollecting ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RefreshCw className="mr-2 h-4 w-4" />
                            )}
                            {isCollecting ? "同步中..." : "刷新数据"}
                        </Button>
                    </div>
                }
            />

            {/* Platform Banner Header - Unique Design element */}
            <div className={cn(
                "relative overflow-hidden rounded-3xl p-8 bg-gradient-to-br border border-black shadow-2xl",
                config.color,
                "opacity-90"
            )}>
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div className="space-y-2">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-white/20 backdrop-blur-md rounded-2xl">
                                <Video className="h-6 w-6 text-white" />
                            </div>
                            <h2 className="text-2xl font-bold text-white">{config.label}矩阵数据概览</h2>
                        </div>
                        <p className="text-white/80 max-w-md">
                            当前已监控 {videoCount} 个视频，覆盖核心互动指标与传播趋势。
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 md:flex md:gap-8">
                        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 min-w-[120px]">
                            <p className="text-xs text-white/60 mb-1">今日新增播放</p>
                            <div className="flex items-baseline gap-2">
                                <span className="text-xl font-bold text-white">{formatNumber(stats.views)}</span>
                                <Badge className="bg-emerald-500 text-white border-0 text-[10px] h-4">
                                    <ArrowUpRight className="h-2.5 w-2.5 mr-0.5" />
                                    {videoCount}个
                                </Badge>
                            </div>
                        </div>
                        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 min-w-[120px]">
                            <p className="text-xs text-white/60 mb-1">平均互动率</p>
                            <div className="flex items-baseline gap-2">
                                <span className="text-xl font-bold text-white">{stats.engagement}%</span>
                                <Zap className="h-3 w-3 text-yellow-300" />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Background decorative elements */}
                <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
                <div className="absolute -left-20 -bottom-20 h-64 w-64 rounded-full bg-black/10 blur-3xl" />
            </div>

            {/* Dynamic Stats Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {config.stats.map((item, idx) => (
                    <Card key={idx} className="bg-black/40 border-black group hover:border-white/20 transition-all duration-300">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-white/60 group-hover:text-white transition-colors">
                                {item.label}
                            </CardTitle>
                            <div className={cn("p-2 rounded-lg bg-black/60", item.color)}>
                                <item.icon className="h-4 w-4" />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold text-white">
                                {formatNumber((stats as any)[item.key] || 0)}
                            </div>
                            <p className="text-xs text-white/40 mt-1 flex items-center gap-1">
                                <TrendingUp className="h-3 w-3" />
                                较上周期持平
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Main Content Area - 热门视频双栏布局 */}
            <Card className="bg-black/40 border-black overflow-hidden">
                <CardHeader className="border-b border-black/20 bg-black/20">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-lg text-white">热门视频排行</CardTitle>
                            <CardDescription className="text-white/40">基于播放、点赞、评论、收藏、分享的综合评分</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-4">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="h-8 w-8 animate-spin text-white/20" />
                        </div>
                    ) : sortedVideos.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-20 text-white/20 italic">
                            <p>暂无视频数据，请尝试同步</p>
                        </div>
                    ) : (
                        <>
                            {/* 双栏布局 */}
                            <div className="grid md:grid-cols-2 gap-3 mb-4">
                                {/* 左栏 */}
                                <div className="space-y-2">
                                    {hotVideosData.leftColumn.map((video: any, idx: number) => (
                                        <div key={idx} className="group flex items-start gap-2 p-2 rounded-lg bg-black/20 hover:bg-black/40 transition-all border border-black/20 hover:border-white/10">
                                            <div className="relative shrink-0">
                                                <img
                                                    src={video.cover_url || "/placeholder-video.png"}
                                                    className="w-24 h-32 object-cover rounded-lg border border-black"
                                                    alt=""
                                                />
                                                <div className="absolute top-1 left-1 bg-black/80 backdrop-blur-md px-2 py-0.5 rounded-md text-xs text-white/90 font-bold">
                                                    #{(hotVideosPage - 1) * hotVideosPerPage + idx * 2 + 1}
                                                </div>
                                            </div>
                                            <div className="flex-1 min-w-0 flex flex-col">
                                                <h4 className="text-white font-medium line-clamp-2 leading-snug mb-2">
                                                    {video.title || "未命名视频"}
                                                </h4>
                                                <div className="flex items-center gap-2 mb-2 text-xs text-white/50">
                                                    {video.author_avatar ? (
                                                        <img
                                                            src={video.author_avatar}
                                                            className="h-4 w-4 rounded-full object-cover border border-white/10"
                                                            alt=""
                                                        />
                                                    ) : (
                                                        <div className="h-4 w-4 rounded-full bg-white/10" />
                                                    )}
                                                    <span className="truncate">{video.author_name || "作者未填写"}</span>
                                                </div>

                                                {/* 详细数据展示 - 横向一排 */}
                                                <div className="flex items-center gap-3 mb-2">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">播放</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.views)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">点赞</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.likes)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">评论</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.comments)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">收藏</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.collects)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">分享</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.shares)}</span>
                                                    </div>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => handleOpenVideo(video)}
                                                        className="h-6 w-6 p-0 hover:bg-white/10 ml-auto"
                                                        title="在浏览器中打开"
                                                    >
                                                        <ArrowUpRight className="h-3.5 w-3.5 text-white/60 group-hover:text-white transition-colors" />
                                                    </Button>
                                                </div>

                                                <div className="text-[10px] text-white/30 truncate">
                                                    {video.publish_time || "刚刚"}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* 右栏 */}
                                <div className="space-y-2">
                                    {hotVideosData.rightColumn.map((video: any, idx: number) => (
                                        <div key={idx} className="group flex items-start gap-2 p-2 rounded-lg bg-black/20 hover:bg-black/40 transition-all border border-black/20 hover:border-white/10">
                                            <div className="relative shrink-0">
                                                <img
                                                    src={video.cover_url || "/placeholder-video.png"}
                                                    className="w-24 h-32 object-cover rounded-lg border border-black"
                                                    alt=""
                                                />
                                                <div className="absolute top-1 left-1 bg-black/80 backdrop-blur-md px-2 py-0.5 rounded-md text-xs text-white/90 font-bold">
                                                    #{(hotVideosPage - 1) * hotVideosPerPage + idx * 2 + 2}
                                                </div>
                                            </div>
                                            <div className="flex-1 min-w-0 flex flex-col">
                                                <h4 className="text-white font-medium line-clamp-2 leading-snug mb-2">
                                                    {video.title || "未命名视频"}
                                                </h4>
                                                <div className="flex items-center gap-2 mb-2 text-xs text-white/50">
                                                    {video.author_avatar ? (
                                                        <img
                                                            src={video.author_avatar}
                                                            className="h-4 w-4 rounded-full object-cover border border-white/10"
                                                            alt=""
                                                        />
                                                    ) : (
                                                        <div className="h-4 w-4 rounded-full bg-white/10" />
                                                    )}
                                                    <span className="truncate">{video.author_name || "作者未填写"}</span>
                                                </div>

                                                {/* 详细数据展示 - 横向一排 */}
                                                <div className="flex items-center gap-3 mb-2">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">播放</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.views)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">点赞</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.likes)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">评论</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.comments)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">收藏</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.collects)}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-[10px] text-white/50">分享</span>
                                                        <span className="text-xs font-medium text-white">{formatNumber(video.shares)}</span>
                                                    </div>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => handleOpenVideo(video)}
                                                        className="h-6 w-6 p-0 hover:bg-white/10 ml-auto"
                                                        title="在浏览器中打开"
                                                    >
                                                        <ArrowUpRight className="h-3.5 w-3.5 text-white/60 group-hover:text-white transition-colors" />
                                                    </Button>
                                                </div>

                                                <div className="text-[10px] text-white/30 truncate">
                                                    {video.publish_time || "刚刚"}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* 分页控件 */}
                            <div className="flex items-center justify-center gap-2 pt-4 border-t border-black/20">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={hotVideosPage <= 1}
                                    onClick={() => setHotVideosPage(prev => Math.max(1, prev - 1))}
                                    className="border-black bg-black/40 hover:bg-black/60"
                                >
                                    上一页
                                </Button>
                                <span className="text-sm text-white/60">
                                    第 {hotVideosPage} / {hotVideosTotalPages} 页
                                </span>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={hotVideosPage >= hotVideosTotalPages}
                                    onClick={() => setHotVideosPage(prev => Math.min(hotVideosTotalPages, prev + 1))}
                                    className="border-black bg-black/40 hover:bg-black/60"
                                >
                                    下一页
                                </Button>
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Sheet for Full Data Table */}
            <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
                <SheetContent className="w-full sm:max-w-5xl bg-black border-black text-white">
                    <SheetHeader className="pb-6 border-b border-black">
                        <SheetTitle className="text-2xl text-white">{config.label} 视频数据全集</SheetTitle>
                        <SheetDescription>查看所有监测到的视频元数据、互动指标及发布状态</SheetDescription>
                        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-white/60">
                            <span>每页显示</span>
                            <Select value={String(sheetPageSize)} onValueChange={(value) => setSheetPageSize(Number(value))}>
                                <SelectTrigger className="h-8 w-20 border-white/10 bg-black text-white">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {[10, 20, 50, 100].map((size) => (
                                        <SelectItem key={size} value={String(size)}>{size}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <div className="ml-auto flex items-center gap-2 text-white/60">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-3 text-xs"
                                    disabled={sheetPage <= 1}
                                    onClick={() => setSheetPage((prev) => Math.max(1, prev - 1))}
                                >
                                    上一页
                                </Button>
                                <span>{sheetPage} / {sheetTotalPages}</span>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-3 text-xs"
                                    disabled={sheetPage >= sheetTotalPages}
                                    onClick={() => setSheetPage((prev) => Math.min(sheetTotalPages, prev + 1))}
                                >
                                    下一页
                                </Button>
                            </div>
                        </div>
                    </SheetHeader>

                    <div className="mt-6 flex flex-col h-full overflow-hidden pb-10">
                        <ScrollArea className="flex-1">
                            <Table>
                                <TableHeader className="sticky top-0 bg-black z-10 border-b border-black">
                                    <TableRow className="border-black hover:bg-black">
                                        <TableHead className="w-[300px]">视频内容</TableHead>
                                        <TableHead>播放</TableHead>
                                        <TableHead>点赞</TableHead>
                                        <TableHead>评论</TableHead>
                                        <TableHead>收藏</TableHead>
                                        <TableHead>分享</TableHead>
                                        <TableHead>时长</TableHead>
                                        <TableHead>链接</TableHead>
                                        <TableHead>状态</TableHead>
                                        <TableHead>更多</TableHead>
                                        <TableHead className="text-right">发布时间</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {sheetVideos.map((v: any, i: number) => {
                                        const key = rowKey(v, i)
                                        const extras = extractExtraFields(v)
                                        const rawJson = v.raw_data ? JSON.stringify(v.raw_data, null, 2) : ""
                                        const isExpanded = !!expandedRows[key]
                                        return (
                                            <Fragment key={key}>
                                                <TableRow className="border-black hover:bg-white/5 group">
                                                    <TableCell>
                                                        <div className="flex items-center gap-3">
                                                            <img src={v.cover_url} className="h-10 w-8 rounded object-cover border border-black" alt="" />
                                                            <div className="min-w-0">
                                                                <span className="font-medium line-clamp-1">{v.title}</span>
                                                                <div className="mt-1 flex items-center gap-2 text-[11px] text-white/50">
                                                                    {v.author_avatar ? (
                                                                        <img
                                                                            src={v.author_avatar}
                                                                            className="h-3.5 w-3.5 rounded-full object-cover border border-white/10"
                                                                            alt=""
                                                                        />
                                                                    ) : (
                                                                        <div className="h-3.5 w-3.5 rounded-full bg-white/10" />
                                                                    )}
                                                                    <span className="truncate">{v.author_name || "作者未填写"}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="font-mono text-xs">{formatNumber(v.views)}</TableCell>
                                                    <TableCell className="font-mono text-xs">{formatNumber(v.likes)}</TableCell>
                                                    <TableCell className="font-mono text-xs">{formatNumber(v.comments)}</TableCell>
                                                    <TableCell className="font-mono text-xs">{formatNumber(v.collects)}</TableCell>
                                                    <TableCell className="font-mono text-xs">{formatNumber(v.shares)}</TableCell>
                                                    <TableCell className="font-mono text-xs">{formatDuration(v.duration)}</TableCell>
                                                    <TableCell className="text-xs">
                                                        {v.video_url ? (
                                                            <a
                                                                href={v.video_url}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="inline-flex items-center gap-1 text-white/70 hover:text-white"
                                                            >
                                                                查看
                                                                <ArrowUpRight className="h-3.5 w-3.5" />
                                                            </a>
                                                        ) : (
                                                            <span className="text-white/30">-</span>
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-0">在线</Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-7 px-2 text-xs text-white/70 hover:text-white"
                                                            onClick={() => toggleRow(key)}
                                                        >
                                                            {isExpanded ? "收起" : "详情"}
                                                        </Button>
                                                    </TableCell>
                                                    <TableCell className="text-right text-xs text-white/40">{v.publish_time}</TableCell>
                                                </TableRow>
                                                {isExpanded && (
                                                    <TableRow className="border-black bg-black/40">
                                                        <TableCell colSpan={11} className="p-4">
                                                            <div className="grid gap-4 md:grid-cols-3">
                                                                <div className="space-y-2">
                                                                    <div className="text-xs text-white/60">基础字段</div>
                                                                    <div className="grid grid-cols-2 gap-2 text-xs text-white/80">
                                                                        <div>视频ID</div>
                                                                        <div className="text-white/50">{formatValue(v.video_id)}</div>
                                                                        <div>账号</div>
                                                                        <div className="text-white/50">{formatValue(v.account_name || v.account_id)}</div>
                                                                        <div>平台</div>
                                                                        <div className="text-white/50">{formatValue(v.platform)}</div>
                                                                        <div>状态</div>
                                                                        <div className="text-white/50">{formatValue(v.status)}</div>
                                                                        <div>采集时间</div>
                                                                        <div className="text-white/50">{formatValue(v.collected_at)}</div>
                                                                    </div>
                                                                </div>
                                                                <div className="space-y-2">
                                                                    <div className="text-xs text-white/60">平台字段</div>
                                                                    <div className="grid grid-cols-2 gap-2 text-xs text-white/80">
                                                                        {extras.length > 0 ? (
                                                                            extras.map((item, idx) => (
                                                                                <div key={`${key}-extra-${idx}`} className="contents">
                                                                                    <div>{item.label}</div>
                                                                                    <div className="text-white/50">{formatValue(item.value)}</div>
                                                                                </div>
                                                                            ))
                                                                        ) : (
                                                                            <div className="text-white/40">无更多字段</div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                                <div className="space-y-2">
                                                                    <div className="text-xs text-white/60">原始数据</div>
                                                                    <pre className="max-h-56 overflow-auto rounded-lg bg-black/60 p-3 text-[10px] leading-relaxed text-white/70">
                                                                        {rawJson || "{}"}
                                                                    </pre>
                                                                </div>
                                                            </div>
                                                        </TableCell>
                                                    </TableRow>
                                                )}
                                            </Fragment>
                                        )
                                    })}
                                </TableBody>
                            </Table>
                        </ScrollArea>
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    )
}

function ScrollArea({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <div className={cn("overflow-auto", className)}>
            {children}
        </div>
    )
}
