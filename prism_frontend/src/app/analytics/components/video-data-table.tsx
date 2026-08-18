"use client"

import { useState, useMemo } from "react"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ExternalLink, ArrowUpDown, ChevronDown, Eye, SlidersHorizontal, ArrowUp, ArrowDown } from "lucide-react"
import { format } from "date-fns"
import { VideoAnalytics } from "../types"

interface VideoDataTableProps {
    data: VideoAnalytics[]
    isLoading: boolean
}

type SortConfig = {
    key: keyof VideoAnalytics | null
    direction: 'asc' | 'desc'
}

export function VideoDataTable({ data, isLoading }: VideoDataTableProps) {
    // Sorting
    const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'publishDate', direction: 'desc' })

    // Pagination
    const [currentPage, setCurrentPage] = useState(1)
    const pageSize = 10

    // Search
    const [searchQuery, setSearchQuery] = useState("")

    // Column Visibility
    const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>({
        video: true,
        link: true,
        platform: true,
        playCount: true,
        likeCount: true,
        commentCount: true,
        collectCount: true,
        publishDate: true,
        action: true
    })

    // Filter & Sort Data
    const processedData = useMemo(() => {
        let filtered = [...data]

        // Search
        if (searchQuery) {
            const query = searchQuery.toLowerCase()
            filtered = filtered.filter(item =>
                item.title.toLowerCase().includes(query) ||
                item.videoId.toLowerCase().includes(query)
            )
        }

        // Sort
        if (sortConfig.key) {
            filtered.sort((a, b) => {
                // Handle potential undefined values safely
                const aValue = a[sortConfig.key!]
                const bValue = b[sortConfig.key!]

                if (aValue === undefined && bValue === undefined) return 0
                if (aValue === undefined) return 1
                if (bValue === undefined) return -1

                if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1
                if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1
                return 0
            })
        }

        return filtered
    }, [data, searchQuery, sortConfig])

    // Pagination Logic
    const totalPages = Math.ceil(processedData.length / pageSize)
    const paginatedData = processedData.slice(
        (currentPage - 1) * pageSize,
        currentPage * pageSize
    )

    const handleSort = (key: keyof VideoAnalytics) => {
        setSortConfig(current => ({
            key,
            direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc'
        }))
    }

    const formatNumber = (num: number) => {
        if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
        return num.toLocaleString()
    }

    const SortIcon = ({ column }: { column: keyof VideoAnalytics }) => {
        if (sortConfig.key !== column) return <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
        return sortConfig.direction === 'asc'
            ? <ArrowUp className="ml-2 h-4 w-4 text-primary" />
            : <ArrowDown className="ml-2 h-4 w-4 text-primary" />
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 flex-1 max-w-sm">
                    <Input
                        placeholder="搜索视频标题或ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="bg-black/20 border-white/10 text-white placeholder:text-white/40"
                    />
                </div>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button
                            variant="outline"
                            className="ml-auto border-white/10 bg-black/40 text-white/80 hover:text-white hover:bg-black/60 data-[state=open]:bg-white/10 data-[state=open]:text-white transition-all"
                        >
                            <SlidersHorizontal className="mr-2 h-4 w-4" />
                            显示列
                            <ChevronDown className="ml-2 h-3 w-3 opacity-50" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-neutral-900 border-white/10 text-white">
                        {Object.keys(visibleColumns).map((key) => {
                            const labels: Record<string, string> = {
                                video: "视频信息",
                                link: "链接",
                                platform: "平台",
                                playCount: "播放量",
                                likeCount: "点赞",
                                commentCount: "评论",
                                collectCount: "收藏",
                                publishDate: "发布时间",
                                action: "操作"
                            }
                            return (
                                <DropdownMenuCheckboxItem
                                    key={key}
                                    checked={visibleColumns[key]}
                                    onCheckedChange={(checked) =>
                                        setVisibleColumns(prev => ({ ...prev, [key]: checked }))
                                    }
                                    className="hover:bg-white/10 focus:bg-white/10 cursor-pointer"
                                >
                                    {labels[key]}
                                </DropdownMenuCheckboxItem>
                            )
                        })}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

            <div className="rounded-md border border-white/10 overflow-hidden">
                <Table>
                    <TableHeader className="bg-white/5">
                        <TableRow className="border-white/10 hover:bg-white/5">
                            {visibleColumns.video && <TableHead className="text-white/60">视频</TableHead>}
                            {visibleColumns.link && <TableHead className="text-white/60">视频链接</TableHead>}
                            {visibleColumns.platform && <TableHead className="text-white/60">平台</TableHead>}
                            {visibleColumns.playCount && (
                                <TableHead onClick={() => handleSort('playCount')} className="cursor-pointer text-white/60 hover:text-white transition-colors">
                                    <div className="flex items-center">播放量 <SortIcon column="playCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.likeCount && (
                                <TableHead onClick={() => handleSort('likeCount')} className="cursor-pointer text-white/60 hover:text-white transition-colors">
                                    <div className="flex items-center">点赞 <SortIcon column="likeCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.commentCount && (
                                <TableHead onClick={() => handleSort('commentCount')} className="cursor-pointer text-white/60 hover:text-white transition-colors">
                                    <div className="flex items-center">评论 <SortIcon column="commentCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.collectCount && (
                                <TableHead onClick={() => handleSort('collectCount')} className="cursor-pointer text-white/60 hover:text-white transition-colors">
                                    <div className="flex items-center">收藏 <SortIcon column="collectCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.publishDate && (
                                <TableHead onClick={() => handleSort('publishDate')} className="cursor-pointer text-white/60 hover:text-white transition-colors">
                                    <div className="flex items-center">发布时间 <SortIcon column="publishDate" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.action && <TableHead className="text-white/60 text-right">操作</TableHead>}
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {processedData.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={Object.values(visibleColumns).filter(Boolean).length} className="h-24 text-center text-white/40">
                                    {isLoading ? "加载中..." : "暂无数据"}
                                </TableCell>
                            </TableRow>
                        ) : (
                            paginatedData.map((video) => (
                                <TableRow key={video.id} className="border-white/10 hover:bg-white/5 transition-colors">
                                    {visibleColumns.video && (
                                        <TableCell>
                                            <div className="flex items-center gap-3">
                                                <div className="relative w-16 h-9 rounded overflow-hidden bg-neutral-800 shrink-0 border border-white/10">
                                                    <img
                                                        src={video.thumbnail || '/placeholder-video.png'}
                                                        alt={video.title}
                                                        className="w-full h-full object-cover"
                                                    />
                                                </div>
                                                <div className="max-w-[200px]">
                                                    <p className="text-sm font-medium truncate text-white/90" title={video.title}>{video.title}</p>
                                                    <p className="text-xs text-white/40 mt-0.5 truncate">ID: {video.videoId}</p>
                                                </div>
                                            </div>
                                        </TableCell>
                                    )}
                                    {visibleColumns.link && (
                                        <TableCell>
                                            {video.videoUrl ? (
                                                <a
                                                    href={video.videoUrl}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                                >
                                                    查看
                                                    <ExternalLink className="h-3 w-3" />
                                                </a>
                                            ) : (
                                                <span className="text-white/20 text-xs">-</span>
                                            )}
                                        </TableCell>
                                    )}
                                    {visibleColumns.platform && (
                                        <TableCell>
                                            <Badge variant="outline" className="bg-white/5 border-white/10 text-white/70 hover:bg-white/10">
                                                {video.platform}
                                            </Badge>
                                        </TableCell>
                                    )}
                                    {visibleColumns.playCount && (
                                        <TableCell className="font-medium text-blue-400/90">{formatNumber(video.playCount)}</TableCell>
                                    )}
                                    {visibleColumns.likeCount && (
                                        <TableCell className="text-pink-400/90">{formatNumber(video.likeCount)}</TableCell>
                                    )}
                                    {visibleColumns.commentCount && (
                                        <TableCell className="text-cyan-400/90">{formatNumber(video.commentCount)}</TableCell>
                                    )}
                                    {visibleColumns.collectCount && (
                                        <TableCell className="text-green-400/90">{formatNumber(video.collectCount)}</TableCell>
                                    )}
                                    {visibleColumns.publishDate && (
                                        <TableCell className="text-sm text-white/50 font-mono">
                                            {format(new Date(video.publishDate), 'yyyy-MM-dd HH:mm')}
                                        </TableCell>
                                    )}
                                    {visibleColumns.action && (
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 hover:bg-white/10 text-white/60 hover:text-white">
                                                <Eye className="h-4 w-4" />
                                                <span className="sr-only">查看详情</span>
                                            </Button>
                                        </TableCell>
                                    )}
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-end space-x-2 py-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        className="bg-transparent border-white/10 text-white/70 hover:text-white hover:bg-white/10"
                    >
                        上一页
                    </Button>
                    <div className="text-xs text-white/50">
                        {currentPage} / {totalPages}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        className="bg-transparent border-white/10 text-white/70 hover:text-white hover:bg-white/10"
                    >
                        下一页
                    </Button>
                </div>
            )}
        </div>
    )
}
