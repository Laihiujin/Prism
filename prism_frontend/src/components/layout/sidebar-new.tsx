"use client"

import * as React from "react"
import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import {
  BarChart3,
  ChevronsLeft,
  ChevronDown,
  ClipboardList,
  FolderKanban,
  Globe,
  LayoutDashboard,
  LayoutGrid,
  Settings,
  TrendingUp,
  UsersRound,
  Video,
  Boxes,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { HermesLogoIcon } from "@/components/hermes-logo-icon"
import GradientText from "@/components/GradientText"
import { cn } from "@/lib/utils"

const DouyinIcon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex shrink-0 items-center justify-center", className)}>
    <Image src="/douYin.svg" alt="Douyin" width={16} height={16} className="object-contain" />
  </div>
)

const BilibiliIcon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex shrink-0 items-center justify-center", className)}>
    <Image src="/bilibili.svg" alt="Bilibili" width={16} height={16} className="object-contain" />
  </div>
)

const KuaishouIcon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex shrink-0 items-center justify-center", className)}>
    <Image src="/kuaiShou.svg" alt="Kuaishou" width={16} height={16} className="object-contain" />
  </div>
)

const XhsIcon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex shrink-0 items-center justify-center", className)}>
    <Image src="/xiaoHongShu.svg" alt="XHS" width={16} height={16} className="object-contain" />
  </div>
)

const ChannelsIcon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex shrink-0 items-center justify-center", className)}>
    <Image src="/shiPingHao.svg" alt="Channels" width={16} height={16} className="object-contain" />
  </div>
)

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
    label: "概览",
    items: [{ label: "仪表盘", href: "/", icon: LayoutDashboard }],
  },
  {
    label: "资源",
    items: [
      { label: "账号管理", href: "/account", icon: UsersRound },
      { label: "素材管理", href: "/materials", icon: FolderKanban },
      { label: "代理管理", href: "/ip-pool", icon: Globe },
    ],
  },
  {
    label: "分发",
    items: [
      { label: "矩阵发布", href: "/publish/matrix", icon: LayoutGrid },
      { label: "任务管理", href: "/tasks", icon: ClipboardList },
    ],
  },
  {
    label: "数据",
    items: [
      { label: "数据中心", href: "/analytics", icon: BarChart3 },
      {
        label: "视频数据",
        icon: Video,
        children: [
          { label: "抖音", href: "/analytics/videos/douyin", icon: DouyinIcon },
          { label: "B 站", href: "/analytics/videos/bilibili", icon: BilibiliIcon },
          { label: "快手", href: "/analytics/videos/kuaishou", icon: KuaishouIcon },
          { label: "小红书", href: "/analytics/videos/xiaohongshu", icon: XhsIcon },
          { label: "视频号", href: "/analytics/videos/channels", icon: ChannelsIcon },
        ],
      },
      { label: "数据趋势", href: "/analytics/trends", icon: TrendingUp },
    ],
  },
  {
    label: "智能",
    items: [
      { label: "Hermes Agent", href: "/ai-agent", icon: HermesLogoIcon },
      { label: "开发者工具", href: "/tools", icon: Boxes },
    ],
  },
  {
    label: "系统",
    items: [{ label: "系统设置", href: "/settings", icon: Settings }],
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
  onNavigate,
}: SidebarProps) {
  const pathname = usePathname()

  return (
    <div className="relative flex">
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 80 : 280 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className={cn("relative flex h-screen flex-col border-r border-border/80 bg-glass-strong text-foreground", className)}
      >
        <div className="flex h-16 items-center justify-between border-b border-border/80 px-6">
          <AnimatePresence mode="wait">
            {!collapsed ? (
              <motion.div
                key="logo-text"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="flex items-center gap-3"
              >
                <div className="relative">
                  <img src="/logo.png" alt="Prism Logo" className="h-10 w-10 rounded-full object-cover ring-1 ring-border/80" />
                  <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-background bg-white" />
                </div>
                <GradientText
                  colors={["#FFFFFF", "#C8C8C8", "#FFFFFF"]}
                  animationSpeed={14}
                  className="whitespace-nowrap text-base font-semibold tracking-tight !mx-0 !justify-start"
                >Prism</GradientText>
              </motion.div>
            ) : (
              <motion.div
                key="logo-icon"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.3 }}
              >
                <div className="relative">
                  <img src="/logo.png" alt="Prism Logo" className="h-10 w-10 rounded-full object-cover ring-1 ring-border/80" />
                  <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-background bg-white" />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <ScrollArea className="scrollbar-none flex-1 px-3 py-4">
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
                      <h3 className="mb-2 px-3 text-xs font-medium uppercase tracking-wider text-foreground/40">
                        {section.label}
                      </h3>                    </motion.div>
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
                            "text-foreground/70 hover:bg-accent hover:text-accent-foreground",
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
                          {!collapsed && <ChevronDown className="ml-auto h-4 w-4 text-foreground/40" />}
                        </div>
                      )

                      if (collapsed) {
                        return (
                          <TooltipProvider key={item.label} delayDuration={0}>
                            <Tooltip>
                              <TooltipTrigger asChild>{triggerContent}</TooltipTrigger>
                              <TooltipContent side="right" className="border-border bg-background text-foreground">
                                {item.label}
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        )
                      }

                      return (
                        <Collapsible key={item.label} defaultOpen={shouldOpen}>
                          <CollapsibleTrigger asChild>{triggerContent}</CollapsibleTrigger>
                          <CollapsibleContent className="space-y-1 pl-4 pt-1">
                            {item.children?.map((child) => {
                              const ChildIcon = child.icon
                              const childActive = pathname === child.href
                              return (
                                <Link
                                  key={child.label}
                                  href={child.href || "#"}
                                  onClick={() => onNavigate?.()}
                                  className={cn(
                                    "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200",
                                    childActive
                                      ? "bg-gradient-to-r from-primary/20 to-primary/5 text-foreground"
                                      : "text-foreground/60 hover:bg-accent hover:text-accent-foreground",
                                  )}
                                >
                                  <ChildIcon
                                    className={cn(
                                      "h-4 w-4 shrink-0 transition-colors",
                                      childActive ? "text-primary" : "text-foreground/50 group-hover:text-foreground"
                                    )}
                                    suppressHydrationWarning
                                  />
                                  <span className="truncate">{child.label}</span>
                                </Link>
                              )
                            })}
                          </CollapsibleContent>
                        </Collapsible>
                      )
                    }

                    const itemContent = (
                      <Link
                        href={item.href || "#"}
                        onClick={() => onNavigate?.()}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                          isActive
                            ? "bg-gradient-to-r from-primary/20 to-primary/5 text-foreground shadow-[inset_0_1px_0_0_hsl(var(--primary)/0.15)]"
                            : "text-foreground/70 hover:bg-accent hover:text-accent-foreground",
                        )}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-primary shadow-[0_0_12px_hsl(var(--primary)/0.6)]" />
                        )}
                        <Icon
                          className={cn(
                            "relative h-5 w-5 shrink-0 transition-colors",
                            isActive ? "text-primary" : "text-foreground/60 group-hover:text-foreground"
                          )}
                          suppressHydrationWarning
                        />
                        <AnimatePresence mode="wait">
                          {!collapsed && (
                            <motion.span
                              key={`item-${item.label}`}
                              initial={{ opacity: 0, width: 0 }}
                              animate={{ opacity: 1, width: "auto" }}
                              exit={{ opacity: 0, width: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden whitespace-nowrap"
                            >
                              {item.label}
                            </motion.span>
                          )}
                        </AnimatePresence>
                      </Link>
                    )

                    if (collapsed) {
                      return (
                        <TooltipProvider key={item.label} delayDuration={0}>
                          <Tooltip>
                            <TooltipTrigger asChild>{itemContent}</TooltipTrigger>
                            <TooltipContent side="right" className="border-border bg-background text-foreground">
                              {item.label}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )
                    }

                    return <React.Fragment key={item.label}>{itemContent}</React.Fragment>
                  })}
                </div>
              </div>
            ))}
          </nav>
        </ScrollArea>

        {showCollapseToggle && (
          <div className="border-t border-border/80 p-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCollapsed(!collapsed)}
              className="h-10 w-10 rounded-xl text-foreground/70 hover:bg-accent hover:text-accent-foreground"
            >
              <motion.div animate={{ rotate: collapsed ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronsLeft className="h-5 w-5" />
              </motion.div>
            </Button>
          </div>
        )}
      </motion.aside>
    </div>
  )
}
