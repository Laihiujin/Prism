import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Link, Gamepad2, Smartphone, Store, FileText, ImageIcon, Sparkles, CalendarClock } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

interface ConfigProps {
    data: any
    onChange: (data: any) => void
}

/**
 * 读取/写入某平台在 `data.platformSettings.<platform>` 下的一个配置字段。
 * 让各平台配置面板成为受控组件，值持久化到 Plan 并随发布 payload 提交。
 */
function usePlatformField(data: any, onChange: (data: any) => void, platform: string, key: string, initial: any) {
    const value = data?.platformSettings?.[platform]?.[key] ?? initial
    const setValue = (v: any) => {
        const settings = data?.platformSettings || {}
        onChange({
            platformSettings: {
                ...settings,
                [platform]: { ...(settings[platform] || {}), [key]: v },
            },
        })
    }
    return [value, setValue] as const
}

// 抖音小程序/游戏/应用选择对话框
interface MountableItem {
    id: number
    name: string
    type: "游戏" | "小程序" | "应用" | "第三方应用"
    icon: string
    description?: string
}

function MiniProgramDialog({ onSelect, platform = "douyin" }: { onSelect: (item: MountableItem) => void, platform?: string }) {
    const [search, setSearch] = useState("")
    const [activeTab, setActiveTab] = useState<string>("all")

    // 抖音平台的挂载内容
    const douyinItems: MountableItem[] = [
        { id: 1, name: "芒果斗地主", type: "游戏", icon: "🎮", description: "热门休闲游戏" },
        { id: 2, name: "开心消消乐", type: "游戏", icon: "🎮", description: "经典消除游戏" },
        { id: 3, name: "羊了个羊", type: "游戏", icon: "🐑", description: "火爆益智游戏" },
        { id: 4, name: "抖音商城", type: "小程序", icon: "📱", description: "官方电商小程序" },
        { id: 5, name: "美团外卖", type: "小程序", icon: "🍔", description: "在线订餐服务" },
        { id: 6, name: "饿了么", type: "小程序", icon: "🍜", description: "外卖配送平台" },
        { id: 7, name: "滴滴出行", type: "小程序", icon: "🚗", description: "出行服务平台" },
        { id: 8, name: "京东购物", type: "应用", icon: "🛒", description: "电商购物应用" },
        { id: 9, name: "淘宝", type: "应用", icon: "🛍️", description: "综合购物平台" },
        { id: 10, name: "拼多多", type: "第三方应用", icon: "🎁", description: "团购电商平台" },
    ]

    // 快手平台的挂载内容
    const kuaishouItems: MountableItem[] = [
        { id: 11, name: "快手小店", type: "应用", icon: "🏪", description: "快手电商" },
        { id: 12, name: "球球大作战", type: "游戏", icon: "⚽", description: "竞技对战游戏" },
        { id: 13, name: "天天酷跑", type: "游戏", icon: "🏃", description: "跑酷游戏" },
        { id: 14, name: "快手商城", type: "小程序", icon: "🛒", description: "官方商城" },
    ]

    const items = platform === "kuaishou" ? kuaishouItems : douyinItems

    const filteredItems = items.filter(item => {
        const matchesSearch = item.name.toLowerCase().includes(search.toLowerCase())
        const matchesTab = activeTab === "all" || item.type === activeTab
        return matchesSearch && matchesTab
    })

    const tabs = [
        { key: "all", label: "全部" },
        { key: "游戏", label: "游戏" },
        { key: "小程序", label: "小程序" },
        { key: "应用", label: "应用" },
    ]

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                    <Gamepad2 className="w-3 h-3 mr-2" />
                    <span className="text-xs">选择小程序/游戏/应用</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl rounded-none border-border bg-black text-foreground shadow-2xl">
                <DialogHeader>
                    <DialogTitle>选择挂载内容</DialogTitle>
                </DialogHeader>

                {/* 标签页 */}
                <div className="flex gap-2 border-b border-border pb-2">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={cn(
                                "px-3 py-1 text-xs transition-colors",
                                activeTab === tab.key
                                    ? "bg-foreground text-background"
                                    : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
                            )}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                <Input
                    placeholder="搜索小程序、游戏或应用..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="rounded-none bg-black border-border text-foreground placeholder:text-muted-foreground"
                />
                <ScrollArea className="h-[400px]">
                    <div className="grid grid-cols-2 gap-3">
                        {filteredItems.map(item => (
                            <div
                                key={item.id}
                                onClick={() => {
                                    onSelect(item)
                                }}
                                className="flex items-center gap-3 border border-border bg-black p-3 cursor-pointer transition-colors hover:bg-white/[0.06]"
                            >
                                <span className="text-2xl">{item.icon}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium truncate">{item.name}</div>
                                    <div className="text-xs text-muted-foreground truncate">{item.description || item.type}</div>
                                </div>
                                <Badge variant="outline" className="text-[10px] shrink-0 border-border/80">
                                    {item.type}
                                </Badge>
                            </div>
                        ))}
                        {filteredItems.length === 0 && (
                            <div className="col-span-2 text-center py-8 text-foreground/40">
                                未找到相关内容
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </DialogContent>
        </Dialog>
    )
}

// POI地点选择对话框
function POIDialog({ onSelect }: { onSelect: (poi: any) => void }) {
    const [search, setSearch] = useState("")
    const [pois, setPois] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")

    useEffect(() => {
        const query = search.trim()
        if (!query) {
            setPois([])
            setError("")
            return
        }
        const controller = new AbortController()
        const timer = window.setTimeout(async () => {
            setLoading(true)
            setError("")
            try {
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=10&accept-language=zh-CN&q=${encodeURIComponent(query)}`,
                    { signal: controller.signal, headers: { Accept: "application/json" } }
                )
                if (!response.ok) throw new Error("地址搜索服务暂不可用")
                const results = await response.json()
                setPois(results.map((item: any) => ({
                    id: item.place_id,
                    name: item.name || item.display_name.split(",")[0],
                    address: item.display_name,
                    lat: item.lat,
                    lng: item.lon,
                })))
            } catch (cause) {
                if ((cause as Error).name !== "AbortError") setError("地址搜索失败，请稍后重试")
            } finally {
                setLoading(false)
            }
        }, 350)
        return () => { window.clearTimeout(timer); controller.abort() }
    }, [search])

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                    <MapPin className="w-3 h-3 mr-2" />
                    <span className="text-xs">添加位置信息</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="rounded-none border-border bg-black text-foreground shadow-2xl">
                <DialogHeader>
                    <DialogTitle>选择地点</DialogTitle>
                </DialogHeader>
                <Input
                    placeholder="搜索地点..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="rounded-none bg-black border-border text-foreground placeholder:text-muted-foreground"
                />
                <ScrollArea className="h-[300px]">
                    <div className="space-y-2">
                        {loading && <div className="py-8 text-center text-sm text-muted-foreground">正在搜索地址…</div>}
                        {!loading && error && <div className="py-8 text-center text-sm text-red-400">{error}</div>}
                        {!loading && !error && !search.trim() && <div className="py-8 text-center text-sm text-muted-foreground">输入地点或地址开始搜索</div>}
                        {!loading && !error && search.trim() && pois.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">没有找到匹配地址</div>}
                        {!loading && pois.map(poi => (
                                <div
                                    key={poi.id}
                                    onClick={() => onSelect(poi)}
                                    className="flex items-center gap-3 border border-border bg-black p-3 cursor-pointer transition-colors hover:bg-white/[0.06]"
                                >
                                    <MapPin className="w-5 h-5 text-foreground" />
                                    <div className="flex-1">
                                        <div className="text-sm font-medium">{poi.name}</div>
                                        <div className="text-xs text-muted-foreground">{poi.address}</div>
                                    </div>
                                </div>
                            ))}
                    </div>
                </ScrollArea>
            </DialogContent>
        </Dialog>
    )
}

export function DouyinConfig({ data, onChange }: ConfigProps) {
    const [selectedMiniProgram, setSelectedMiniProgram] = usePlatformField(data, onChange, "douyin", "miniProgram", null as MountableItem | null)
    const [selectedPOI, setSelectedPOI] = usePlatformField(data, onChange, "douyin", "poi", null as any)
    const [coverOrientation, setCoverOrientation] = usePlatformField(data, onChange, "douyin", "coverOrientation", "landscape" as "landscape" | "portrait")
    const [useAIRandomCover, setUseAIRandomCover] = usePlatformField(data, onChange, "douyin", "useAIRandomCover", false)
    const [coverFile, setCoverFile] = usePlatformField(data, onChange, "douyin", "coverFile", "" as string)
    const [collection, setCollection] = usePlatformField(data, onChange, "douyin", "collection", "" as string)
    const [declaration, setDeclaration] = usePlatformField(data, onChange, "douyin", "declaration", "" as string)
    const [hotspot, setHotspot] = usePlatformField(data, onChange, "douyin", "hotspot", "" as string)
    const [whoCanSee, setWhoCanSee] = usePlatformField(data, onChange, "douyin", "whoCanSee", "公开" as string)
    const [savePermission, setSavePermission] = usePlatformField(data, onChange, "douyin", "savePermission", "允许" as "允许" | "不允许")
    const [timing, setTiming] = usePlatformField(data, onChange, "douyin", "timing", "立即发布" as "立即发布" | "定时发布")
    const [publishDatetime, setPublishDatetime] = usePlatformField(data, onChange, "douyin", "publishDatetime", "" as string)

    // 自主声明选项（复刻真实弹窗的单选项）
    const declarationOptions = [
        { key: "不涉及", label: "不涉及（无需声明）" },
        { key: "AI生成", label: "使用AI工具生成" },
        { key: "二创", label: "二次创作/剪辑" },
        { key: "演绎", label: "剧情演绎/表演" },
        { key: "广告", label: "含广告/推广" },
        { key: "知识科普", label: "知识科普" },
    ]

    const segBtn = (active: boolean) => cn(
        "flex-1 px-2 py-1.5 text-xs rounded-md border transition-all",
        active ? "bg-foreground text-background border-foreground"
               : "text-muted-foreground border-border/70 hover:bg-accent/40 hover:text-foreground"
    )

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">抖音配置</h3>
                <Badge variant="outline" className="text-[10px] border-white/17 text-white">抖音</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载小程序/游戏/应用 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载内容
                    </Label>
                    <MiniProgramDialog onSelect={setSelectedMiniProgram} platform="douyin" />
                    {selectedMiniProgram && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <span className="text-2xl">{selectedMiniProgram.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground">{selectedMiniProgram.name}</div>
                                <div className="text-[10px] text-muted-foreground">{selectedMiniProgram.description}</div>
                            </div>
                            <Badge variant="outline" className="text-[10px] shrink-0 border-white/17 text-white">
                                {selectedMiniProgram.type}
                            </Badge>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setSelectedMiniProgram(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        添加地点
                    </Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <MapPin className="w-4 h-4 text-white" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-foreground truncate">{selectedPOI.name}</div>
                                <div className="text-[10px] text-muted-foreground truncate">{selectedPOI.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50"
                                onClick={() => setSelectedPOI(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 封面：横/竖 + 上传 + AI 智能推荐随机 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <ImageIcon className="w-3 h-3" />
                        封面
                    </Label>
                    <div className="flex gap-2">
                        <button className={segBtn(coverOrientation === "landscape")} onClick={() => setCoverOrientation("landscape")}>
                            横封面 4:3
                        </button>
                        <button className={segBtn(coverOrientation === "portrait")} onClick={() => setCoverOrientation("portrait")}>
                            竖封面 3:4
                        </button>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-border/70 bg-card/20 px-3 py-2">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Sparkles className="w-3 h-3 text-primary" />
                            AI 智能推荐封面（随机）
                        </div>
                        <Switch checked={useAIRandomCover} onCheckedChange={setUseAIRandomCover} />
                    </div>
                    <input
                        type="file"
                        accept="image/*"
                        id="douyin-cover-upload"
                        className="hidden"
                        onChange={e => setCoverFile(e.target.files?.[0]?.name || "")}
                    />
                    <label
                        htmlFor="douyin-cover-upload"
                        className="inline-flex items-center justify-center gap-2 w-full h-9 px-3 text-xs rounded-md border border-border/70 bg-card/20 text-muted-foreground hover:bg-accent/40 hover:text-foreground cursor-pointer transition-all"
                    >
                        <ImageIcon className="w-3 h-3" />
                        {coverFile || "上传封面图片"}
                    </label>
                </div>

                {/* 合集 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        合集
                    </Label>
                    <Select value={collection} onValueChange={setCollection}>
                        <SelectTrigger className="w-full h-9 text-xs bg-card/20 border-border/70">
                            <SelectValue placeholder="请选择合集" />
                        </SelectTrigger>
                        <SelectContent className="rounded-none bg-black text-foreground border-border/70">
                            <SelectItem value="">不加入合集</SelectItem>
                            <SelectItem value="合集1">合集 · 生活日常</SelectItem>
                            <SelectItem value="合集2">合集 · 美食探店</SelectItem>
                            <SelectItem value="合集3">合集 · 旅行日记</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* 自主声明：弹窗单选 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        自主声明
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                                <span className="text-xs">{declaration || "请选择自主声明"}</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="rounded-none bg-black border-border/70 text-foreground">
                            <DialogHeader>
                                <DialogTitle>对作品内容添加声明</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-2 mt-2">
                                {declarationOptions.map(opt => (
                                    <div
                                        key={opt.key}
                                        onClick={() => setDeclaration(opt.label)}
                                        className={cn(
                                            "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                                            declaration === opt.label
                                                ? "border-foreground bg-accent/40"
                                                : "border-border/70 bg-black hover:bg-white/[0.06]"
                                        )}
                                    >
                                        <span className={cn(
                                            "w-4 h-4 rounded-full border flex items-center justify-center text-[9px]",
                                            declaration === opt.label ? "border-foreground bg-foreground text-background" : "border-border"
                                        )}>
                                            {declaration === opt.label ? "✓" : ""}
                                        </span>
                                        <span className="text-sm">{opt.label}</span>
                                    </div>
                                ))}
                            </div>
                            <DialogClose asChild>
                                <Button className="w-full mt-3">确定</Button>
                            </DialogClose>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* 关联热点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Link className="w-3 h-3" />
                        关联热点
                    </Label>
                    <Input
                        placeholder="点击输入热点词"
                        value={hotspot}
                        onChange={e => setHotspot(e.target.value)}
                        className="bg-card/20 border-border/70 h-9 text-xs"
                    />
                </div>

                {/* 谁可以看 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">谁可以看</Label>
                    <div className="flex gap-2">
                        {["公开", "好友可见", "仅自己可见"].map(opt => (
                            <button key={opt} className={segBtn(whoCanSee === opt)} onClick={() => setWhoCanSee(opt)}>
                                {opt}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 保存权限 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">保存权限</Label>
                    <div className="flex items-center justify-between rounded-lg border border-border/70 bg-card/20 px-3 py-2">
                        <span className="text-xs text-muted-foreground">允许他人保存作品</span>
                        <Switch checked={savePermission === "允许"} onCheckedChange={v => setSavePermission(v ? "允许" : "不允许")} />
                    </div>
                </div>

                {/* 发布时间 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <CalendarClock className="w-3 h-3" />
                        发布时间
                    </Label>
                    <div className="flex gap-2">
                        <button className={segBtn(timing === "立即发布")} onClick={() => setTiming("立即发布")}>立即发布</button>
                        <button className={segBtn(timing === "定时发布")} onClick={() => setTiming("定时发布")}>定时发布</button>
                    </div>
                    {timing === "定时发布" && (
                        <Input
                            placeholder="YYYY-MM-DD HH:MM"
                            value={publishDatetime}
                            onChange={e => setPublishDatetime(e.target.value)}
                            className="bg-card/20 border-border/70 h-9 text-xs"
                        />
                    )}
                </div>
            </div>
        </div>
    )
}

export function KuaishouConfig({ data, onChange }: ConfigProps) {
    const [selectedGame, setSelectedGame] = usePlatformField(data, onChange, "kuaishou", "game", null as MountableItem | null)
    const [selectedPOI, setSelectedPOI] = usePlatformField(data, onChange, "kuaishou", "poi", null as any)

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">快手配置</h3>
                <Badge variant="outline" className="text-[10px] border-white/17 text-white">快手</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载游戏/应用 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载游戏或应用
                    </Label>
                    <MiniProgramDialog onSelect={setSelectedGame} platform="kuaishou" />
                    {selectedGame && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <span className="text-2xl">{selectedGame.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground">{selectedGame.name}</div>
                                <div className="text-[10px] text-muted-foreground">{selectedGame.description}</div>
                            </div>
                            <Badge variant="outline" className="text-[10px] shrink-0 border-white/17 text-white">
                                {selectedGame.type}
                            </Badge>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setSelectedGame(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        添加地点
                    </Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <MapPin className="w-4 h-4 text-white" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-foreground truncate">{selectedPOI.name}</div>
                                <div className="text-[10px] text-muted-foreground truncate">{selectedPOI.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50"
                                onClick={() => setSelectedPOI(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export function XhsConfig({ data, onChange }: ConfigProps) {
    const [selectedPOI, setSelectedPOI] = usePlatformField(data, onChange, "xiaohongshu", "poi", null as any)

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">小红书配置</h3>
                <Badge variant="outline" className="text-[10px] border-white/17 text-white">小红书</Badge>
            </div>

            <div className="grid gap-4">
                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">添加地点</Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-2 rounded-lg bg-black border border-primary/30">
                            <MapPin className="w-4 h-4 text-primary" />
                            <span className="text-xs text-foreground truncate">{selectedPOI.name}</span>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="ml-auto h-6 w-6 p-0 hover:bg-accent/50"
                                onClick={() => setSelectedPOI(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 话题标签 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">话题标签</Label>
                    <Input
                        placeholder="输入话题，用空格分隔"
                        className="bg-card/20 border-border/70 text-xs"
                    />
                    <p className="text-[10px] text-foreground/40">例如：#美食 #探店 #生活分享</p>
                </div>
            </div>
        </div>
    )
}

export function BilibiliConfig({ data, onChange }: ConfigProps) {
    const [selectedGame, setSelectedGame] = usePlatformField(data, onChange, "bilibili", "game", null as MountableItem | null)
    const [category, setCategory] = usePlatformField(data, onChange, "bilibili", "category", "生活")

    // B站专属游戏列表
    const bilibiliGames: MountableItem[] = [
        { id: 101, name: "原神", type: "游戏", icon: "⚔️", description: "开放世界冒险游戏" },
        { id: 102, name: "英雄联盟", type: "游戏", icon: "🎮", description: "MOBA竞技游戏" },
        { id: 103, name: "王者荣耀", type: "游戏", icon: "👑", description: "移动端MOBA" },
        { id: 104, name: "我的世界", type: "游戏", icon: "🧱", description: "沙盒建造游戏" },
        { id: 105, name: "崩坏：星穹铁道", type: "游戏", icon: "🚂", description: "回合制RPG" },
    ]

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">B站配置</h3>
                <Badge variant="outline" className="text-[10px] border-white/17 text-white">B站</Badge>
            </div>

            <div className="space-y-4">
                {/* 挂载游戏 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载游戏
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                                <Gamepad2 className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择游戏</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="rounded-none bg-black border-border/70 text-foreground max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择游戏</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="grid grid-cols-2 gap-3">
                                    {bilibiliGames.map(game => (
                                        <div
                                            key={game.id}
                                            onClick={() => setSelectedGame(game)}
                                            className="flex items-center gap-3 p-3 rounded-none border border-border/70 bg-black hover:bg-white/[0.06] cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{game.icon}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{game.name}</div>
                                                <div className="text-xs text-muted-foreground truncate">{game.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedGame && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <span className="text-2xl">{selectedGame.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground">{selectedGame.name}</div>
                                <div className="text-[10px] text-muted-foreground">{selectedGame.description}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setSelectedGame(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 分区选择 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">分区</Label>
                    <div className="flex flex-wrap gap-2">
                        {["生活", "游戏", "娱乐", "知识", "科技"].map(option => (
                            <button
                                key={option}
                                type="button"
                                aria-pressed={category === option}
                                onClick={() => setCategory(option)}
                                className={cn(
                                    "cursor-pointer border px-3 py-1 text-xs transition-colors",
                                    category === option
                                        ? "border-foreground bg-foreground text-background"
                                        : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                                )}
                            >
                                {option}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 标签 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">标签</Label>
                    <Input
                        placeholder="按回车键输入标签"
                        className="bg-card/20 border-border/70 text-xs"
                        value={data.tags ? (Array.isArray(data.tags) ? data.tags.join(' ') : data.tags) : ""}
                        onChange={(e) => onChange({ ...data, tags: e.target.value.split(' ') })}
                    />
                    <p className="text-[10px] text-foreground/40">使用空格分隔多个标签</p>
                </div>
            </div>
        </div>
    )
}

export function VideoChannelConfig({ data, onChange }: ConfigProps) {
    const [selectedArticle, setSelectedArticle] = usePlatformField(data, onChange, "channels", "article", null as any)
    const [selectedMiniProgram, setSelectedMiniProgram] = usePlatformField(data, onChange, "channels", "miniProgram", null as MountableItem | null)
    const [selectedLocation, setSelectedLocation] = usePlatformField(data, onChange, "channels", "location", null as any)

    // 视频号专属小程序列表
    const wechatMiniPrograms: MountableItem[] = [
        { id: 201, name: "微信小商店", type: "小程序", icon: "🛍️", description: "官方电商小程序" },
        { id: 202, name: "京东购物", type: "小程序", icon: "🛒", description: "京东官方小程序" },
        { id: 203, name: "拼多多", type: "小程序", icon: "🎁", description: "拼单购物小程序" },
        { id: 204, name: "美团外卖", type: "小程序", icon: "🍔", description: "在线订餐服务" },
        { id: 205, name: "滴滴出行", type: "小程序", icon: "🚗", description: "出行服务平台" },
    ]

    // 公众号文章列表（示例）
    const articles = [
        { id: 1, title: "如何提升视频播放量", date: "2024-01-15", cover: "📄" },
        { id: 2, title: "短视频运营技巧分享", date: "2024-01-10", cover: "📄" },
        { id: 3, title: "视频号变现指南", date: "2024-01-05", cover: "📄" },
    ]

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">视频号配置</h3>
                <Badge variant="outline" className="text-[10px] border-white/17 text-white">视频号</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载公众号文章 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        挂载公众号文章
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                                <FileText className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择公众号文章</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="rounded-none bg-black border-border/70 text-foreground max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择公众号文章</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="space-y-2">
                                    {articles.map(article => (
                                        <div
                                            key={article.id}
                                            onClick={() => setSelectedArticle(article)}
                                            className="flex items-center gap-3 p-3 rounded-none border border-border/70 bg-black hover:bg-white/[0.06] cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{article.cover}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{article.title}</div>
                                                <div className="text-xs text-muted-foreground">{article.date}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedArticle && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <FileText className="w-4 h-4 text-white" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground truncate">{selectedArticle.title}</div>
                                <div className="text-[10px] text-muted-foreground">{selectedArticle.date}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setSelectedArticle(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 挂载小程序 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Smartphone className="w-3 h-3" />
                        挂载小程序
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                                <Smartphone className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择小程序</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="rounded-none bg-black border-border/70 text-foreground max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择小程序</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="grid grid-cols-2 gap-3">
                                    {wechatMiniPrograms.map(mini => (
                                        <div
                                            key={mini.id}
                                            onClick={() => setSelectedMiniProgram(mini)}
                                            className="flex items-center gap-3 p-3 rounded-none border border-border/70 bg-black hover:bg-white/[0.06] cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{mini.icon}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{mini.name}</div>
                                                <div className="text-xs text-muted-foreground truncate">{mini.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedMiniProgram && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <span className="text-2xl">{selectedMiniProgram.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground">{selectedMiniProgram.name}</div>
                                <div className="text-[10px] text-muted-foreground">{selectedMiniProgram.description}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setSelectedMiniProgram(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 所在位置 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        所在位置
                    </Label>
                    <POIDialog onSelect={setSelectedLocation} />
                    {selectedLocation && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-white/17">
                            <MapPin className="w-4 h-4 text-white" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-foreground truncate">{selectedLocation.name}</div>
                                <div className="text-[10px] text-muted-foreground truncate">{selectedLocation.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50"
                                onClick={() => setSelectedLocation(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
