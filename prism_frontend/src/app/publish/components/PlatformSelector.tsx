import { cn } from "@/lib/utils"
import Image from "next/image"

export const PLATFORMS = [
    { key: "douyin", name: "抖音", code: 3, icon: "/douYin.svg", desc: "抖音矩阵多元组合", disabled: false },
    { key: "kuaishou", name: "快手", code: 4, icon: "/kuaiShou.svg", desc: "快手矩阵多元组合", disabled: false },
    { key: "channels", name: "视频号", code: 2, icon: "/shiPingHao.svg", desc: "视频号矩阵多元组合", disabled: false },
    { key: "xiaohongshu", name: "小红书", code: 1, icon: "/xiaoHongShu.svg", desc: "小红书矩阵多元组合", disabled: false },
    { key: "bilibili", name: "B站", code: 5, icon: "/bilibili.svg", desc: "B站矩阵多元组合", disabled: false },
    { key: "tiktok", name: "TikTok", code: 6, icon: "/Tiktok.svg", desc: "TikTok Studio 发布", disabled: false },
    { key: "youtube", name: "YouTube", code: 7, icon: "/youtube.svg", desc: "YouTube Studio 发布", disabled: false },
] as const

export type PlatformKey = typeof PLATFORMS[number]["key"]

interface PlatformSelectorProps {
    selected: PlatformKey[]
    onSelect: (key: PlatformKey) => void
}

export function PlatformSelector({ selected, onSelect }: PlatformSelectorProps) {
    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {PLATFORMS.map((platform) => {
                const isSelected = selected.includes(platform.key)
                return (
                    <button
                        key={platform.key}
                        onClick={() => !platform.disabled && onSelect(platform.key)}
                        disabled={platform.disabled}
                        className={cn(
                            "relative flex items-center gap-3 p-4 rounded-xl border text-left transition-all group",
                            isSelected
                                ? "border-primary bg-black ring-1 ring-primary"
                                : "border-border/70 bg-card hover:bg-accent/50 hover:border-border/80",
                            platform.disabled && "opacity-50 cursor-not-allowed"
                        )}
                    >
                        {isSelected && (
                            <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgba(var(--primary),0.5)]" />
                        )}
                        <div className="w-10 h-10 relative shrink-0 transition-transform group-hover:scale-110">
                            <Image
                                src={platform.icon}
                                alt={platform.name}
                                fill
                                className="object-contain"
                            />
                        </div>
                        <div className="min-w-0">
                            <div className="font-medium text-sm text-foreground">{platform.name}</div>
                            <div className="text-[10px] text-muted-foreground truncate">{platform.desc}</div>
                        </div>
                    </button>
                )
            })}
        </div>
    )
}
