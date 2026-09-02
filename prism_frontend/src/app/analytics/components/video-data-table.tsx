"use client"

import { useState, useMemo, useEffect } from "react"
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

    useEffect(() => {
        if (currentPage > Math.max(1, totalPages)) setCurrentPage(1)
    }, [currentPage, totalPages])

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
        <div className="space-y-2">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 flex-1 max-w-sm">
                    <Input
                        placeholder="搜索视频标题或ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-8 bg-card/20 border-border/70 text-xs text-foreground placeholder:text-foreground/40"
                    />
                </div>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button
                            variant="outline"
                            className="ml-auto h-8 border-border/70 bg-card/40 px-2.5 text-xs text-foreground/80 hover:text-foreground hover:bg-card/60 data-[state=open]:bg-black data-[state=open]:text-foreground transition-all"
                        >
                            <SlidersHorizontal className="mr-1.5 h-3.5 w-3.5" />
                            显示列
                            <ChevronDown className="ml-2 h-3 w-3 opacity-50" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44 bg-black border-border/70 p-1 text-foreground">
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
                                    className="h-7 whitespace-nowrap py-1 pl-7 pr-2 text-xs leading-none hover:bg-accent/50 focus:bg-black cursor-pointer"
                                >
                                    {labels[key]}
                                </DropdownMenuCheckboxItem>
                            )
                        })}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

            <div className="border-y border-border/60 overflow-hidden">
                <Table>
                    <TableHeader className="bg-black/80">
                        <TableRow className="h-8 border-border/70 hover:bg-transparent">
                            {visibleColumns.video && <TableHead className="w-[28%] text-[10px] uppercase tracking-wider text-muted-foreground">视频</TableHead>}
                            {visibleColumns.link && <TableHead className="w-16 text-[10px] uppercase tracking-wider text-muted-foreground">链接</TableHead>}
                            {visibleColumns.platform && <TableHead className="w-24 text-[10px] uppercase tracking-wider text-muted-foreground">平台</TableHead>}
                            {visibleColumns.playCount && (
                                <TableHead onClick={() => handleSort('playCount')} className="w-20 cursor-pointer text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                                    <div className="flex items-center">播放量 <SortIcon column="playCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.likeCount && (
                                <TableHead onClick={() => handleSort('likeCount')} className="w-16 cursor-pointer text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                                    <div className="flex items-center">点赞 <SortIcon column="likeCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.commentCount && (
                                <TableHead onClick={() => handleSort('commentCount')} className="w-16 cursor-pointer text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                                    <div className="flex items-center">评论 <SortIcon column="commentCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.collectCount && (
                                <TableHead onClick={() => handleSort('collectCount')} className="w-16 cursor-pointer text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                                    <div className="flex items-center">收藏 <SortIcon column="collectCount" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.publishDate && (
                                <TableHead onClick={() => handleSort('publishDate')} className="w-32 cursor-pointer text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                                    <div className="flex items-center">发布时间 <SortIcon column="publishDate" /></div>
                                </TableHead>
                            )}
                            {visibleColumns.action && <TableHead className="w-12 text-[10px] text-muted-foreground text-right">操作</TableHead>}
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {processedData.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={Object.values(visibleColumns).filter(Boolean).length} className="h-24 text-center text-foreground/40">
                                    {isLoading ? "加载中..." : "暂无数据"}
                                </TableCell>
                            </TableRow>
                        ) : (
                            paginatedData.map((video) => (
                                <TableRow key={video.id} className="h-11 border-border/60 hover:bg-white/[0.03] transition-colors">
                                    {visibleColumns.video && (
                                        <TableCell className="py-1.5">
                                            <div className="flex items-center gap-2">
                                                <div className="relative w-12 h-7 overflow-hidden bg-black shrink-0 border border-border/70">
                                                    <img
                                                        src={video.thumbnail || '/placeholder-video.png'}
                                                        alt={video.title}
                                                        className="w-full h-full object-cover"
                                                    />
                                                </div>
                                                <div className="min-w-0 max-w-[260px]">
                                                    <p className="truncate text-xs font-medium text-foreground/90" title={video.title}>{video.title}</p>
                                                    <p className="mt-0.5 truncate text-[10px] text-foreground/35">{video.videoId}</p>
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
                                                    className="inline-flex items-center gap-1 border border-border/60 bg-black px-1.5 py-0.5 text-[10px] text-white hover:bg-accent/50 hover:text-white transition-colors"
                                                >
                                                    查看
                                                    <ExternalLink className="h-3 w-3" />
                                                </a>
                                            ) : (
                                                <span className="text-foreground/20 text-xs">-</span>
                                            )}
                                        </TableCell>
                                    )}
                                    {visibleColumns.platform && (
                                        <TableCell>
                                            <Badge variant="outline" className="bg-black px-1.5 py-0 text-[10px] border-border/70 text-foreground/70 hover:bg-accent/50">
                                                {video.platform}
                                            </Badge>
                                        </TableCell>
                                    )}
                                    {visibleColumns.playCount && (
                                        <TableCell className="font-mono text-xs font-medium text-white/90">{formatNumber(video.playCount)}</TableCell>
                                    )}
                                    {visibleColumns.likeCount && (
                                        <TableCell className="font-mono text-xs text-white/90">{formatNumber(video.likeCount)}</TableCell>
                                    )}
                                    {visibleColumns.commentCount && (
                                        <TableCell className="font-mono text-xs text-white/90">{formatNumber(video.commentCount)}</TableCell>
                                    )}
                                    {visibleColumns.collectCount && (
                                        <TableCell className="font-mono text-xs text-white/90">{formatNumber(video.collectCount)}</TableCell>
                                    )}
                                    {visibleColumns.publishDate && (
                                        <TableCell className="text-[10px] text-muted-foreground font-mono">
                                            {format(new Date(video.publishDate), 'yyyy-MM-dd HH:mm')}
                                        </TableCell>
                                    )}
                                    {visibleColumns.action && (
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0 hover:bg-accent/50 text-muted-foreground hover:text-foreground">
                                                <Eye className="h-3.5 w-3.5" />
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
            <div className="flex items-center justify-between border-t border-border/60 py-2 text-xs text-muted-foreground">
                    <span>{processedData.length} 条记录 · 每页 {pageSize} 条</span>
                    <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        className="h-7 bg-transparent border-border/70 px-2 text-xs text-foreground/70 hover:text-foreground hover:bg-accent/50"
                    >
                        上一页
                    </Button>
                    <div className="min-w-14 text-center text-xs text-muted-foreground">
                        {currentPage} / {totalPages}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        className="h-7 bg-transparent border-border/70 px-2 text-xs text-foreground/70 hover:text-foreground hover:bg-accent/50"
                    >
                        下一页
                    </Button>
                    </div>
            </div>
        </div>
    )
}
