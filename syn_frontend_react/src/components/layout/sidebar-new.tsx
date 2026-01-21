"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
    LayoutDashboard,
    LayoutGrid,
    UsersRound,
    FolderKanban,
    UploadCloud,
    Calendar,
    ClipboardList,
    QrCode,
    BarChart3,
    ChevronsLeft,
    Video,
    TrendingUp,
    Bot,
    Settings,
    Globe,
    ChevronDown,
} from "lucide-react"
import Image from "next/image"

const DouyinIcon = ({ className }: { className?: string }) => (
    <div className={cn("relative flex items-center justify-center shrink-0", className)}>
        <Image src="/douYin.svg" alt="Douyin" width={16} height={16} className="object-contain" />
    </div>
)

const BilibiliIcon = ({ className }: { className?: string }) => (
    <div className={cn("relative flex items-center justify-center shrink-0", className)}>
        <Image src="/bilibili.svg" alt="Bilibili" width={16} height={16} className="object-contain" />
    </div>
)

const KuaishouIcon = ({ className }: { className?: string }) => (
    <div className={cn("relative flex items-center justify-center shrink-0", className)}>
        <Image src="/kuaiShou.svg" alt="Kuaishou" width={16} height={16} className="object-contain" />
    </div>
)

const XhsIcon = ({ className }: { className?: string }) => (
    <div className={cn("relative flex items-center justify-center shrink-0", className)}>
        <Image src="/xiaoHongShu.svg" alt="XHS" width={16} height={16} className="object-contain" />
    </div>
)

const ChannelsIcon = ({ className }: { className?: string }) => (
    <div className={cn("relative flex items-center justify-center shrink-0", className)}>
        <Image src="/shiPingHao.svg" alt="Channels" width={16} height={16} className="object-contain" />
    </div>
)

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"

interface NavItem {
    label: string
    href?: string
    icon: React.ElementType
    disabled?: boolean
    external?: boolean
    children?: NavItem[]
}

interface NavSection {
    label: string
    items: NavItem[]
}

const navSections: NavSection[] = [
    {
        label: "Overview",
        items: [
            { label: "仪表盘", href: "/", icon: LayoutDashboard },
        ],
    },
    {
        label: "Assets",
        items: [
            { label: "账号管理", href: "/account", icon: UsersRound },
            { label: "素材管理", href: "/materials", icon: FolderKanban },
            { label: "IP资源池", href: "/ip-pool", icon: Globe },
        ],
    },
    {
        label: "Distribution",
        items: [
            // { label: "投放计划", href: "/campaigns", icon: Calendar },
            { label: "矩阵发布", href: "/publish/matrix", icon: LayoutGrid },
            { label: "任务管理", href: "/tasks", icon: ClipboardList },
            // { label: "扫码派发", href: "/tasks/distribution", icon: QrCode },
        ],
    },
    {
        label: "Analytics",
        items: [
            { label: "数据中心", href: "/analytics", icon: BarChart3 },
            {
                label: "视频数据",
                icon: Video,
                children: [
                    { label: "抖音", href: "/analytics/videos/douyin", icon: DouyinIcon },
                    { label: "B站", href: "/analytics/videos/bilibili", icon: BilibiliIcon },
                    { label: "快手", href: "/analytics/videos/kuaishou", icon: KuaishouIcon },
                    { label: "小红书", href: "/analytics/videos/xiaohongshu", icon: XhsIcon },
                    { label: "视频号", href: "/analytics/videos/channels", icon: ChannelsIcon },
                ],
            },
            { label: "数据趋势", href: "/analytics/trends", icon: TrendingUp },
        ],
    },
    {
        label: "AI",
        items: [
            { label: "SynapseAI", href: "/ai-agent", icon: Bot },
            // { label: "AI配置", href: "/ai-agent/settings", icon: Settings },
        ],
    },
    {
        label: "System",
        items: [
            { label: "系统设置", href: "/settings", icon: Settings },
        ],
    },
]

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
    collapsed: boolean
    setCollapsed: (collapsed: boolean) => void
    showCollapseToggle?: boolean
    onNavigate?: () => void
}

export function SidebarNew({
    className,
    collapsed,
    setCollapsed,
    showCollapseToggle = true,
    onNavigate
}: SidebarProps) {
    const pathname = usePathname()

    return (
        <div className="relative flex">
            <motion.aside
                initial={false}
                animate={{ width: collapsed ? 80 : 280 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className={cn(
                    "relative flex h-screen flex-col border-r border-white/10 bg-black text-white",
                    className
                )}
            >
                <div className="flex h-16 items-center justify-between border-b border-white/10 px-6">
                    <AnimatePresence mode="wait">
                        {!collapsed && (
                            <motion.div
                                key="logo-text"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.3 }}
                                className="flex items-center gap-3"
                            >
                                <img
                                    src="/default.png"
                                    alt="Synapse Logo"
                                    className="h-10 w-10 rounded-full object-cover"
                                />
                                <span className="text-base font-semibold tracking-tight whitespace-nowrap">SynapseAutomation</span>
                            </motion.div>
                        )}
                        {collapsed && (
                            <motion.div
                                key="logo-icon"
                                initial={{ opacity: 0, scale: 0.8 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.8 }}
                                transition={{ duration: 0.3 }}
                            >
                                <img
                                    src="/default.png"
                                    alt="Synapse Logo"
                                    className="h-10 w-10 rounded-full object-cover"
                                />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <ScrollArea className="flex-1 px-3 py-4 scrollbar-none">
                    <nav className="space-y-6">
                        {navSections.map((section) => (
                            <div key={section.label} className="space-y-1">
                                <AnimatePresence mode="wait">
                                    {!collapsed && (
                                        <motion.div
                                            key={`section-${section.label}`}
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            exit={{ opacity: 0, height: 0 }}
                                            transition={{ duration: 0.2 }}
                                        >
                                            <h3 className="mb-2 px-3 text-xs font-medium uppercase tracking-wider text-white/40">
                                                {section.label}
                                            </h3>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                                <div className="space-y-1">
                                    {section.items.map((item) => {
                                        const Icon = item.icon
                                        const isActive = item.href ? pathname === item.href : false
                                        const hasChildren = (item.children?.length ?? 0) > 0

                                        if (hasChildren) {
                                            const shouldOpen = pathname.startsWith("/analytics/videos")
                                            const triggerContent = (
                                                <div
                                                    className={cn(
                                                        "group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                                                        "text-white/70 hover:bg-white/5 hover:text-white"
                                                    )}
                                                >
                                                    <Icon className="relative h-5 w-5 shrink-0" suppressHydrationWarning />
                                                    <AnimatePresence mode="wait">
                                                        {!collapsed && (
                                                            <motion.span
                                                                key={`text-${item.label}`}
                                                                initial={{ opacity: 0, width: 0 }}
                                                                animate={{ opacity: 1, width: "auto" }}
                                                                exit={{ opacity: 0, width: 0 }}
                                                                transition={{ duration: 0.2 }}
                                                                className="relative overflow-hidden whitespace-nowrap"
                                                            >
                                                                {item.label}
                                                            </motion.span>
                                                        )}
                                                    </AnimatePresence>
                                                    {!collapsed && (
                                                        <ChevronDown className="ml-auto h-4 w-4 text-white/40" />
                                                    )}
                                                </div>
                                            )

                                            if (collapsed) {
                                                return (
                                                    <TooltipProvider key={item.label} delayDuration={0}>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>{triggerContent}</TooltipTrigger>
                                                            <TooltipContent side="right" className="border-white/10 bg-black text-white">
                                                                {item.label}
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    </TooltipProvider>
                                                )
                                            }

                                            return (
                                                <Collapsible key={item.label} defaultOpen={shouldOpen}>
                                                    <CollapsibleTrigger asChild>
                                                        <button type="button" className="w-full text-left">
                                                            {triggerContent}
                                                        </button>
                                                    </CollapsibleTrigger>
                                                    <CollapsibleContent className="mt-1 space-y-1 pl-8">
                                                        {item.children?.map((child) => {
                                                            const childActive = child.href ? pathname === child.href : false
                                                            return (
                                                                <Link
                                                                    key={child.href || child.label}
                                                                    href={child.href || "#"}
                                                                    onClick={() => onNavigate?.()}
                                                                    className={cn(
                                                                        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-xs font-medium transition-all duration-200",
                                                                        childActive
                                                                            ? "bg-white/10 text-white shadow-lg shadow-white/5"
                                                                            : "text-white/60 hover:bg-white/5 hover:text-white"
                                                                    )}
                                                                >
                                                                    {child.icon && <child.icon className="h-4 w-4" />}
                                                                    <span className="relative overflow-hidden whitespace-nowrap">{child.label}</span>
                                                                </Link>
                                                            )
                                                        })}
                                                    </CollapsibleContent>
                                                </Collapsible>
                                            )
                                        }

                                        const linkContent = item.external ? (
                                            <a
                                                key={item.href}
                                                href={item.href}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                onClick={() => onNavigate?.()}
                                                className={cn(
                                                    "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                                                    "text-white/70 hover:bg-white/5 hover:text-white"
                                                )}
                                            >
                                                <Icon className="relative h-5 w-5 shrink-0" suppressHydrationWarning />
                                                <AnimatePresence mode="wait">
                                                    {!collapsed && (
                                                        <motion.span
                                                            key={`text-${item.label}`}
                                                            initial={{ opacity: 0, width: 0 }}
                                                            animate={{ opacity: 1, width: "auto" }}
                                                            exit={{ opacity: 0, width: 0 }}
                                                            transition={{ duration: 0.2 }}
                                                            className="relative overflow-hidden whitespace-nowrap"
                                                        >
                                                            {item.label}
                                                        </motion.span>
                                                    )}
                                                </AnimatePresence>
                                            </a>
                                        ) : (
                                            <Link
                                                key={item.href || item.label}
                                                href={item.disabled ? "#" : (item.href || "#")}
                                                onClick={() => {
                                                    if (!item.disabled) onNavigate?.()
                                                }}
                                                className={cn(
                                                    "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                                                    isActive
                                                        ? "bg-white/10 text-white shadow-lg shadow-white/5"
                                                        : "text-white/70 hover:bg-white/5 hover:text-white",
                                                    item.disabled && "cursor-not-allowed opacity-50"
                                                )}
                                                aria-disabled={item.disabled}
                                            >
                                                {isActive && (
                                                    <motion.div
                                                        layoutId="active-pill"
                                                        className="absolute inset-0 rounded-xl bg-white/10"
                                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                                    />
                                                )}
                                                <Icon className="relative h-5 w-5 shrink-0" suppressHydrationWarning />
                                                <AnimatePresence mode="wait">
                                                    {!collapsed && (
                                                        <motion.span
                                                            key={`text-${item.label}`}
                                                            initial={{ opacity: 0, width: 0 }}
                                                            animate={{ opacity: 1, width: "auto" }}
                                                            exit={{ opacity: 0, width: 0 }}
                                                            transition={{ duration: 0.2 }}
                                                            className="relative overflow-hidden whitespace-nowrap"
                                                        >
                                                            {item.label}
                                                        </motion.span>
                                                    )}
                                                </AnimatePresence>
                                            </Link>
                                        )

                                        if (collapsed) {
                                            return (
                                                <TooltipProvider key={item.href || item.label} delayDuration={0}>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                                                        <TooltipContent side="right" className="border-white/10 bg-black text-white">
                                                            {item.label}
                                                        </TooltipContent>
                                                    </Tooltip>
                                                </TooltipProvider>
                                            )
                                        }

                                        return linkContent
                                    })}
                                </div>
                            </div>
                        ))}
                    </nav>
                </ScrollArea>

                <div className="border-t border-white/10 p-4">
                    <AnimatePresence mode="wait">
                        {!collapsed && (
                            <motion.div
                                key="footer-text"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="text-xs text-white/40"
                            >
                                {/* <p>© 2024 Synapse</p> */}
                                {/* <p className="mt-1">v1.0.0</p> */}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </motion.aside>

            {/* Permanent Toggle Button (desktop only) */}
            {showCollapseToggle && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setCollapsed(!collapsed)}
                    className={cn(
                        "absolute top-4 z-50 hidden h-8 w-8 rounded-full border border-white/10 bg-black shadow-lg transition-all hover:bg-white/10 md:inline-flex",
                        collapsed ? "left-[72px]" : "left-[272px]"
                    )}
                    aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
                >
                    <motion.div
                        animate={{ rotate: collapsed ? 180 : 0 }}
                        transition={{ duration: 0.3 }}
                    >
                        <ChevronsLeft className="h-4 w-4" />
                    </motion.div>
                </Button>
            )}
        </div>
    )
}
