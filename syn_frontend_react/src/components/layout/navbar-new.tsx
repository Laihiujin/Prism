"use client"

import type { ElementType, HTMLAttributes } from "react"
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react"
import {
  BarChart3,
  ClipboardList,
  FolderKanban,
  Globe,
  LayoutDashboard,
  LayoutGrid,
  Menu,
  Search,
  Settings,
  TrendingUp,
  UsersRound,
  Video,
} from "lucide-react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import debounce from "lodash.debounce"

import { HermesLogoIcon } from "@/components/hermes-logo-icon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

interface NavbarProps extends HTMLAttributes<HTMLDivElement> {
  isConnected?: boolean
  environment?: string
  onMenuClick?: () => void
}

interface SearchRoute {
  category: string
  description: string
  href: string
  icon: ElementType
  keywords: string[]
  label: string
}

const ROUTE_CATALOG: SearchRoute[] = [
  {
    category: "概览",
    label: "仪表盘",
    description: "回到系统首页和总览面板",
    href: "/",
    icon: LayoutDashboard,
    keywords: ["home", "dashboard", "overview", "首页", "仪表盘", "总览"],
  },
  {
    category: "资源",
    label: "账号管理",
    description: "查看和维护账号状态",
    href: "/account",
    icon: UsersRound,
    keywords: ["accounts", "users", "账号", "账户", "cookie"],
  },
  {
    category: "资源",
    label: "素材管理",
    description: "管理视频、图片和文件素材",
    href: "/materials",
    icon: FolderKanban,
    keywords: ["materials", "assets", "files", "素材", "文件"],
  },
  {
    category: "资源",
    label: "IP 资源池",
    description: "查看代理和 IP 资源状态",
    href: "/ip-pool",
    icon: Globe,
    keywords: ["ip", "proxy", "network", "资源池", "代理"],
  },
  {
    category: "分发",
    label: "矩阵发布",
    description: "进入矩阵发布流程",
    href: "/publish/matrix",
    icon: LayoutGrid,
    keywords: ["publish", "matrix", "distribution", "发布", "矩阵"],
  },
  {
    category: "分发",
    label: "任务管理",
    description: "查看执行任务和状态",
    href: "/tasks",
    icon: ClipboardList,
    keywords: ["tasks", "jobs", "queue", "任务", "调度"],
  },
  {
    category: "数据",
    label: "数据中心",
    description: "查看整体分析数据",
    href: "/analytics",
    icon: BarChart3,
    keywords: ["analytics", "stats", "report", "数据", "分析"],
  },
  {
    category: "数据",
    label: "抖音视频数据",
    description: "打开抖音视频分析页",
    href: "/analytics/videos/douyin",
    icon: Video,
    keywords: ["douyin", "video", "analytics", "抖音", "视频数据"],
  },
  {
    category: "数据",
    label: "B站视频数据",
    description: "打开 B 站视频分析页",
    href: "/analytics/videos/bilibili",
    icon: Video,
    keywords: ["bilibili", "video", "analytics", "b站", "视频数据"],
  },
  {
    category: "数据",
    label: "快手视频数据",
    description: "打开快手视频分析页",
    href: "/analytics/videos/kuaishou",
    icon: Video,
    keywords: ["kuaishou", "video", "analytics", "快手", "视频数据"],
  },
  {
    category: "数据",
    label: "小红书视频数据",
    description: "打开小红书视频分析页",
    href: "/analytics/videos/xiaohongshu",
    icon: Video,
    keywords: ["xiaohongshu", "video", "analytics", "小红书", "视频数据"],
  },
  {
    category: "数据",
    label: "视频号数据",
    description: "打开视频号分析页",
    href: "/analytics/videos/channels",
    icon: Video,
    keywords: ["channels", "wechat", "video", "视频号", "视频数据"],
  },
  {
    category: "数据",
    label: "数据趋势",
    description: "查看趋势和变化曲线",
    href: "/analytics/trends",
    icon: TrendingUp,
    keywords: ["trends", "growth", "图表", "趋势", "变化"],
  },
  {
    category: "智能",
    label: "Hermes Agent",
    description: "进入 Hermes 智能助手",
    href: "/ai-agent",
    icon: HermesLogoIcon,
    keywords: ["hermes", "agent", "ai", "助手", "智能"],
  },
  {
    category: "系统",
    label: "系统设置",
    description: "调整运行时和应用设置",
    href: "/settings",
    icon: Settings,
    keywords: ["settings", "system", "config", "设置", "系统"],
  },
]

const CATEGORY_ORDER = ["概览", "资源", "分发", "数据", "智能", "系统"] as const

function buildSearchUrl(pathname: string, searchParams: URLSearchParams, term: string) {
  const params = new URLSearchParams(searchParams.toString())
  if (term) {
    params.set("q", term)
  } else {
    params.delete("q")
  }

  const query = params.toString()
  return query ? `${pathname}?${query}` : pathname
}

export function NavbarNew({ className, onMenuClick }: NavbarProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()

  const currentQuery = searchParams.get("q")?.toString() ?? ""
  const [searchValue, setSearchValue] = useState(currentQuery)
  const [isFocused, setIsFocused] = useState(false)
  const deferredSlashQuery = useDeferredValue(
    searchValue.startsWith("/") ? searchValue.slice(1).trim().toLowerCase() : ""
  )

  const syncSearchParam = useMemo(
    () =>
      debounce((term: string, paramsSnapshot: string, nextPathname: string) => {
        const nextUrl = buildSearchUrl(nextPathname, new URLSearchParams(paramsSnapshot), term)
        startTransition(() => {
          router.replace(nextUrl)
        })
      }, 250),
    [router]
  )

  useEffect(() => {
    return () => {
      syncSearchParam.cancel()
    }
  }, [syncSearchParam])

  const slashResults = useMemo(() => {
    if (!searchValue.startsWith("/")) {
      return []
    }

    return ROUTE_CATALOG.filter((route) => {
      if (!deferredSlashQuery) {
        return true
      }

      const haystack = [route.label, route.description, route.href, ...route.keywords]
        .join(" ")
        .toLowerCase()

      return haystack.includes(deferredSlashQuery)
    })
  }, [deferredSlashQuery, searchValue])

  const groupedResults = useMemo(() => {
    return CATEGORY_ORDER.map((category) => ({
      category,
      items: slashResults.filter((route) => route.category === category),
    })).filter((group) => group.items.length > 0)
  }, [slashResults])

  const firstRoute = groupedResults.flatMap((group) => group.items)[0] ?? null
  const inputValue = searchValue.startsWith("/") || isFocused ? searchValue : currentQuery
  const showSlashResults = isFocused && searchValue.startsWith("/")

  const navigateToRoute = (route: SearchRoute) => {
    syncSearchParam.cancel()
    setSearchValue("")
    setIsFocused(false)
    startTransition(() => {
      router.push(route.href)
    })
  }

  const handleChange = (value: string) => {
    setSearchValue(value)

    if (value.startsWith("/")) {
      syncSearchParam.cancel()
      const nextUrl = buildSearchUrl(pathname, new URLSearchParams(searchParams.toString()), "")
      startTransition(() => {
        router.replace(nextUrl)
      })
      return
    }

    syncSearchParam(value, searchParams.toString(), pathname)
  }

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn(
        "sticky top-0 z-50 flex h-16 items-center justify-between border-b border-white/10 bg-black/40 px-6 backdrop-blur-xl relative",
        className
      )}
    >
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden text-white/70 hover:text-white hover:bg-white/10"
            onClick={onMenuClick}
            aria-label="打开菜单"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}
      </div>

      <div className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 md:block">
        <div className="group relative w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-hover:text-white" />
          <Input
            value={inputValue}
            placeholder="Search... 输入 / 跳转页面"
            className="h-9 w-full rounded-2xl border-white/10 bg-black pl-9 pr-12 text-sm text-white transition-all focus:w-[22rem] focus:border-white/20 focus:bg-black focus:shadow-glow-white/10"
            onChange={(event) => handleChange(event.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => {
              window.setTimeout(() => setIsFocused(false), 120)
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setIsFocused(false)
                return
              }

              if (event.key === "Enter" && searchValue.startsWith("/") && firstRoute) {
                event.preventDefault()
                navigateToRoute(firstRoute)
              }
            }}
          />
          <Badge
            variant="outline"
            className="pointer-events-none absolute right-3 top-1/2 h-5 -translate-y-1/2 border-white/10 bg-white/5 px-1.5 font-mono text-[10px] text-white/45"
          >
            /
          </Badge>

          {showSlashResults && (
            <div className="absolute left-0 right-0 top-[calc(100%+0.75rem)] overflow-hidden rounded-2xl border border-white/10 bg-neutral-950/95 shadow-2xl backdrop-blur-xl">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-[0.18em] text-white/40">Page Search</span>
                  <Badge variant="secondary" className="border border-white/10 bg-white/5 text-[10px] text-white/55">
                    Slash
                  </Badge>
                </div>
                <span className="text-xs text-white/35">Enter 跳转首项</span>
              </div>

              <ScrollArea className="max-h-80">
                {groupedResults.length > 0 ? (
                  <div className="p-2">
                    {groupedResults.map((group) => (
                      <div key={group.category} className="mb-2 last:mb-0">
                        <div className="px-2 py-2 text-[11px] font-medium uppercase tracking-[0.18em] text-white/35">
                          {group.category}
                        </div>
                        <div className="space-y-1">
                          {group.items.map((route) => {
                            const Icon = route.icon
                            return (
                              <button
                                key={route.href}
                                type="button"
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() => navigateToRoute(route)}
                                className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-white/75 transition hover:bg-white/8 hover:text-white"
                              >
                                <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5">
                                  <Icon className="h-4 w-4" />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="truncate text-sm font-medium text-white">{route.label}</div>
                                  <div className="truncate text-xs text-white/40">{route.description}</div>
                                </div>
                                <span className="shrink-0 text-[11px] text-white/30">{route.href}</span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="px-4 py-6 text-sm text-white/45">未找到匹配页面</div>
                )}
              </ScrollArea>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4" />
    </motion.header>
  )
}
