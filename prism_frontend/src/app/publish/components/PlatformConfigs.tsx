import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Link, Gamepad2, Smartphone, Store, FileText, ImageIcon, Sparkles, CalendarClock, Music2, X } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

// 发布内容形态：视频 / 图文（图片笔记）
export type PublishContentKind = "video" | "note"
export const CONTENT_KINDS: { value: PublishContentKind; label: string; hint: string }[] = [
    { value: "video", label: "视频", hint: "上传单个视频素材" },
    { value: "note", label: "图文/笔记", hint: "上传多张图片（需先在素材库添加图片素材）" },
]

/**
 * 内容形态切换条：写入 platformSettings.<platform>.contentKind。
 * 支持图文的平台(kindSupported)展示切换；否则固定 video。
 */
function ContentKindSwitch({
    data,
    onChange,
    platform,
    kindSupported = false,
    onKindChange,
}: {
    data: any
    onChange: (data: any) => void
    platform: string
    kindSupported?: boolean
    onKindChange?: (kind: PublishContentKind) => void
}) {
    const [kind, setKind] = usePlatformField(data, onChange, platform, "contentKind", "video" as PublishContentKind)
    if (!kindSupported) return null
    const segBtn = (active: boolean) => cn(
        "flex-1 px-2 py-1.5 text-xs rounded-md border transition-all",
        active ? "bg-foreground text-background border-foreground"
               : "text-muted-foreground border-border/70 hover:bg-accent/40 hover:text-foreground"
    )
    return (
        <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">内容形态</Label>
            <div className="flex gap-2">
                {CONTENT_KINDS.map(opt => (
                    <button
                        key={opt.value}
                        type="button"
                        className={segBtn(kind === opt.value)}
                        onClick={() => {
                            setKind(opt.value)
                            onKindChange?.(opt.value)
                        }}
                    >
                        {opt.label}
                    </button>
                ))}
            </div>
            <p className="text-[10px] text-foreground/40">
                {CONTENT_KINDS.find(k => k.value === kind)?.hint}
            </p>
        </div>
    )
}

export { ContentKindSwitch }

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

// 挂载对象（小程序/游戏/应用/公众号文章）。真实列表在平台发布页联想产生，
// 前端只采集结构化输入：名称（搜索词）+ 类型 + 可选链接（抖音支持直接粘贴链接）。
interface MountableItem {
    id: string
    name: string
    type: string
    url?: string
    description?: string
}

// 挂载对话框：真实化输入（无 demo/mock 候选）。
// 平台发布页的挂载候选是账号维度的实时数据（需登录态联想/弹窗），前端无法离线枚举，
// 因此对话框让用户填「名称/链接」→ 发布时由 uploader 在页面搜索/粘贴。
function MiniProgramDialog({ onSelect, platform = "douyin" }: { onSelect: (item: MountableItem) => void, platform?: string }) {
    const [name, setName] = useState("")
    const [type, setType] = useState("小程序")
    const [url, setUrl] = useState("")
    const [open, setOpen] = useState(false)

    const reset = () => { setName(""); setType("小程序"); setUrl("") }

    const submit = () => {
        const n = name.trim()
        if (!n) return
        onSelect({
            id: `mount-${platform}-${Date.now()}`,
            name: n,
            type,
            url: url.trim() || undefined,
        })
        reset()
        setOpen(false)
    }

    // 平台相关类型标签（抖音挂载对象真实下拉：小程序 / 游戏 / 应用）
    const typeOptions = platform === "bilibili"
        ? ["游戏"]
        : ["小程序", "游戏", "应用"]

    return (
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset() }}>
            <DialogTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-muted-foreground border-border/70 bg-card/20 h-9 hover:bg-accent/40 hover:text-foreground">
                    <Gamepad2 className="w-3 h-3 mr-2" />
                    <span className="text-xs">添加挂载内容（小程序/游戏/应用）</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="rounded-none border-border bg-black text-foreground shadow-2xl">
                <DialogHeader>
                    <DialogTitle>添加挂载内容</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    {/* 类型 */}
                    <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">类型</Label>
                        <div className="flex flex-wrap gap-2">
                            {typeOptions.map((t) => (
                                <button
                                    key={t}
                                    type="button"
                                    aria-pressed={type === t}
                                    onClick={() => setType(t)}
                                    className={cn(
                                        "cursor-pointer border px-3 py-1 text-xs transition-colors",
                                        type === t
                                            ? "border-foreground bg-foreground text-background"
                                            : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                                    )}
                                >
                                    {t}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 名称/搜索词 */}
                    <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">名称/搜索关键词 *</Label>
                        <Input
                            autoFocus
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit() } }}
                            placeholder="如：芒果斗地主 / 抖音商城（发布时在页面联想点选）"
                            className="rounded-none bg-black border-border text-foreground placeholder:text-muted-foreground"
                        />
                        <p className="text-[10px] text-foreground/35 leading-4">
                            抖音发布时在「添加标签 → 小程序」中搜索该名称并点选首个匹配项；
                            若给出链接则直接粘贴到小程序链接输入框。找不到会在日志提示人工核对，不阻断发布。
                        </p>
                    </div>

                    {/* 链接（可选，抖音支持直贴） */}
                    <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">
                            小程序链接（可选）
                            <span className="ml-1 text-[10px] text-foreground/30 font-normal">抖音界面选择「小程序」后若出现链接输入框则直贴此链接</span>
                        </Label>
                        <Input
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="粘贴抖音小程序链接（如 sslocal://xxx）"
                            className="rounded-none bg-black border-border text-foreground placeholder:text-muted-foreground"
                        />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" className="border-border/70" onClick={() => setOpen(false)}>
                            取消
                        </Button>
                        <Button onClick={submit} disabled={!name.trim()}>
                            添加
                        </Button>
                    </div>
                </div>
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
    const [bgm, setBgm] = usePlatformField(data, onChange, "douyin", "bgm", "" as string)
    const [declaration, setDeclaration] = usePlatformField(data, onChange, "douyin", "declaration", "" as string)
    const [hotspot, setHotspot] = usePlatformField(data, onChange, "douyin", "hotspot", "" as string)
    const [whoCanSee, setWhoCanSee] = usePlatformField(data, onChange, "douyin", "whoCanSee", "公开" as string)
    const [savePermission, setSavePermission] = usePlatformField(data, onChange, "douyin", "savePermission", "允许" as "允许" | "不允许")
    const [timing, setTiming] = usePlatformField(data, onChange, "douyin", "timing", "立即发布" as "立即发布" | "定时发布")
    const [publishDatetime, setPublishDatetime] = usePlatformField(data, onChange, "douyin", "publishDatetime", "" as string)

    // 自主声明选项 —— 文案须与抖音发布页「对作品内容添加声明」弹窗的真实单选项一致
    // （实测见 docs/douyin-publish-features.md §5.12：内容由AI生成/个人观点/转载信息/营销推广/虚构演绎/无需添加自主声明）。
    // 若此处文案与平台不匹配，set_self_declaration 会匹配不到 → 弹窗残留 → 发布按钮超时。
    const declarationOptions = [
        { key: "不涉及", label: "无需添加自主声明" },
        { key: "AI生成", label: "内容由AI生成" },
        { key: "个人观点", label: "内容为个人观点或见解" },
        { key: "转载", label: "内容为转载信息" },
        { key: "广告", label: "内容含营销推广信息" },
        { key: "演绎", label: "虚构演绎，仅供娱乐" },
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
                <Badge variant="outline" className="text-[10px] border-border text-white">抖音</Badge>
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
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-border">
                            <Gamepad2 className="w-4 h-4 text-white shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground truncate">{selectedMiniProgram.name}</div>
                                {selectedMiniProgram.url && (
                                    <div className="text-[10px] text-muted-foreground truncate">{selectedMiniProgram.url}</div>
                                )}
                            </div>
                            <Badge variant="outline" className="text-[10px] shrink-0 border-border text-white">
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
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-border">
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
                    <Select value={collection || "none"} onValueChange={(v) => setCollection(v === "none" ? "" : v)}>
                        <SelectTrigger className="w-full h-9 text-xs bg-card/20 border-border/70">
                            <SelectValue placeholder="请选择合集" />
                        </SelectTrigger>
                        <SelectContent className="rounded-none bg-black text-foreground border-border/70">
                            <SelectItem value="none">不加入合集</SelectItem>
                            <SelectItem value="合集1">合集 · 生活日常</SelectItem>
                            <SelectItem value="合集2">合集 · 美食探店</SelectItem>
                            <SelectItem value="合集3">合集 · 旅行日记</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* BGM / 音乐（图集/图文可选） */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Music2 className="w-3 h-3" />
                        BGM 音乐
                        <span className="text-[10px] text-foreground/30 font-normal">（图集/图文可选，抖音发布页内搜索应用）</span>
                    </Label>
                    <div className="flex items-center gap-2">
                        <Input
                            value={bgm}
                            onChange={(e) => setBgm(e.target.value)}
                            placeholder="输入音乐名，如：晴天"
                            className="h-9 text-xs bg-card/20 border-border/70 flex-1"
                        />
                        {bgm && (
                            <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground shrink-0"
                                onClick={() => setBgm("")}
                            >
                                <X className="w-3.5 h-3.5" />
                            </Button>
                        )}
                    </div>
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
    const [selectedPOI, setSelectedPOI] = usePlatformField(data, onChange, "kuaishou", "poi", null as any)

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">快手配置</h3>
                <Badge variant="outline" className="text-[10px] border-border text-white">快手</Badge>
            </div>

            <div className="grid gap-4">
                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        添加地点
                    </Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-border">
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
                <Badge variant="outline" className="text-[10px] border-border text-white">小红书</Badge>
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
    const [category, setCategory] = usePlatformField(data, onChange, "bilibili", "category", "生活")
    const [tid, setTid] = usePlatformField(data, onChange, "bilibili", "tid", 160)
    const [copyright, setCopyright] = usePlatformField(data, onChange, "bilibili", "copyright", 1)
    const [source, setSource] = usePlatformField(data, onChange, "bilibili", "source", "")
    const [dynamic, setDynamic] = usePlatformField(data, onChange, "bilibili", "dynamic", "")

    // B站分区（tid）常用列表：与 category 文案联动
    const bilibiliCategories: { label: string; tid: number }[] = [
        { label: "生活", tid: 160 },
        { label: "游戏", tid: 17 },
        { label: "娱乐", tid: 71 },
        { label: "知识", tid: 207 },
        { label: "科技", tid: 188 },
        { label: "音乐", tid: 3 },
        { label: "舞蹈", tid: 129 },
        { label: "影视", tid: 181 },
    ]

    const selectCategory = (label: string) => {
        const found = bilibiliCategories.find(c => c.label === label)
        // 一次 onChange 写 category + tid，避免两次 usePlatformField setter
        // 基于同一份旧 data 先后合并导致后写覆盖前写（分区点了不生效）。
        const settings = data?.platformSettings || {}
        onChange({
            platformSettings: {
                ...settings,
                bilibili: {
                    ...(settings.bilibili || {}),
                    category: label,
                    tid: found ? found.tid : tid,
                },
            },
        })
    }

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">B站配置</h3>
                <Badge variant="outline" className="text-[10px] border-border text-white">B站</Badge>
            </div>

            <div className="space-y-4">
                {/* 分区选择（tid） */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">分区</Label>
                    <div className="flex flex-wrap gap-2">
                        {bilibiliCategories.map(option => (
                            <button
                                key={option.label}
                                type="button"
                                aria-pressed={category === option.label}
                                onClick={() => selectCategory(option.label)}
                                className={cn(
                                    "cursor-pointer border px-3 py-1 text-xs transition-colors",
                                    category === option.label
                                        ? "border-foreground bg-foreground text-background"
                                        : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                                )}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                    <p className="text-[10px] text-foreground/40">当前 tid：{tid}（不在此列的细分分区请后续在发布时补充）</p>
                </div>

                {/* 版权：自制 / 转载 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">版权</Label>
                    <div className="flex gap-2">
                        {([{ v: 1, label: "自制" }, { v: 2, label: "转载" }]).map(opt => (
                            <button
                                key={opt.v}
                                type="button"
                                aria-pressed={copyright === opt.v}
                                onClick={() => setCopyright(opt.v)}
                                className={cn(
                                    "cursor-pointer border px-3 py-1 text-xs transition-colors",
                                    copyright === opt.v
                                        ? "border-foreground bg-foreground text-background"
                                        : "border-border/70 bg-black text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                                )}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 转载来源 */}
                {copyright === 2 && (
                    <div className="space-y-2">
                        <Label className="text-xs text-muted-foreground">转载来源</Label>
                        <Input
                            placeholder="填写原作品来源（转载时建议填写）"
                            className="bg-card/20 border-border/70 text-xs"
                            value={source || ""}
                            onChange={(e) => setSource(e.target.value)}
                        />
                    </div>
                )}

                {/* 粉丝动态 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">粉丝动态（可选）</Label>
                    <Input
                        placeholder="发布时同步到粉丝动态的文案"
                        className="bg-card/20 border-border/70 text-xs"
                        value={dynamic || ""}
                        onChange={(e) => setDynamic(e.target.value)}
                    />
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

                {/* 分P提示 */}
                <div className="rounded-xl border border-dashed border-border/70 bg-card/20 px-3 py-2 text-[11px] leading-4 text-muted-foreground">
                    分P（多P）发布请使用工具 <code className="font-mono">publish_multipart_to_bilibili</code>（MCP / API / CLI）：
                    一次提交一个稿件、按顺序上传 P1..Pn；矩阵面板的多素材默认按「每个素材一个稿件」分发。
                </div>
            </div>
        </div>
    )
}

export function VideoChannelConfig({ data, onChange }: ConfigProps) {
    // articleUrl：视频号「关联 → 公众号文章 → 粘贴链接」（无确认按钮，见 channels skill）
    const [articleUrl, setArticleUrl] = usePlatformField(data, onChange, "channels", "articleUrl", "" as string)
    // miniProgram：挂载小程序（视频号发布页「关联」区；此处采集名称/链接）
    const [miniProgramName, setMiniProgramName] = usePlatformField(data, onChange, "channels", "miniProgramName", "" as string)
    const [selectedLocation, setSelectedLocation] = usePlatformField(data, onChange, "channels", "location", null as any)

    const articleSummary = (() => {
        if (!articleUrl) return null
        const trimmed = articleUrl.replace(/^https?:\/\//, "")
        return trimmed.length > 46 ? trimmed.slice(0, 46) + "…" : trimmed
    })()

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">视频号配置</h3>
                <Badge variant="outline" className="text-[10px] border-border text-white">视频号</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载公众号文章（真实链接粘贴：发布时平台「关联 → 公众号文章」粘贴 URL） */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        挂载公众号文章
                    </Label>
                    <Input
                        value={articleUrl || ""}
                        onChange={(e) => setArticleUrl(e.target.value)}
                        placeholder="粘贴公众号文章链接（发布时在「关联 → 公众号文章」填入）"
                        className="bg-card/20 border-border/70 text-xs"
                    />
                    <p className="text-[10px] text-foreground/35">需账号在公众号后台有对应发表记录；发布页选择「关联 → 公众号文章」后自动粘贴此链接。</p>
                    {articleSummary && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-border">
                            <FileText className="w-4 h-4 text-white shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="text-[11px] text-muted-foreground truncate">{articleSummary}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-accent/50 shrink-0"
                                onClick={() => setArticleUrl("")}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 挂载小程序（视频号「关联 → 小程序短剧」弹窗按名称搜索点选） */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <Smartphone className="w-3 h-3" />
                        挂载小程序（短剧）
                    </Label>
                    <Input
                        value={miniProgramName || ""}
                        onChange={(e) => setMiniProgramName(e.target.value)}
                        placeholder="小程序/短剧名称，发布时弹窗搜索点选"
                        className="bg-card/20 border-border/70 text-xs"
                    />
                    <p className="text-[10px] text-foreground/35">发布时在「关联 → 小程序短剧」弹窗中按此名称搜索并点选首行；无匹配则点表格首行兜底，失败不阻断发布。</p>
                </div>

                {/* 所在位置 */}
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        所在位置
                    </Label>
                    <POIDialog onSelect={setSelectedLocation} />
                    {selectedLocation && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-white/10 to-white/10 border border-border">
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

export function TwitterConfig({ data, onChange }: ConfigProps) {
    const title = String((data as any)?.title || "")
    const description = String((data as any)?.description || "")
    const rawTags = (data as any)?.tags || []
    const tags = Array.isArray(rawTags) ? rawTags.map((t: string) => `#${String(t || "").trim().replace(/^#/, "")}`.trim()).filter(Boolean) : []
    const tweet = [title, description].filter(Boolean).join("\n\n") + (tags.length ? "\n\n" + tags.join(" ") : "")
    const count = tweet.length

    return (
        <div className="space-y-4 p-5 bg-card rounded-2xl border border-border/70 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground/80">推特配置</h3>
                <Badge variant="outline" className="text-[10px] border-border text-white">X / Twitter</Badge>
            </div>

            <div className="grid gap-4">
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        推文正文预览（标题 + 描述 + 话题）
                    </Label>
                    <div className="rounded-lg border border-border/70 bg-black p-3 text-xs leading-5 text-foreground/90 whitespace-pre-wrap break-words min-h-[72px]">
                        {tweet || <span className="text-foreground/30">将在素材元数据的标题 / 描述 / 话题填入后生成</span>}
                    </div>
                    <p className={`text-[10px] ${count > 280 ? "text-red-400" : "text-foreground/40"}`}>
                        {count} / 280 字符{count > 280 ? "（超出会被截断）" : ""}
                    </p>
                </div>

                <div className="rounded-xl border border-dashed border-border/70 bg-card/20 px-3 py-2 text-[11px] leading-4 text-muted-foreground">
                    <p>发布链路：素材媒体（视频/图片）先经 <code className="font-mono">xurl media upload</code> 上传，再用 <code className="font-mono">xurl post</code> 附上媒体发布。</p>
                    <p className="mt-1">账号需在运行后端的主机上用 <code className="font-mono">xurl auth oauth2 --app &lt;app&gt;</code> 完成一次登录（绑定到 <code className="font-mono">~/.xurl</code>）。</p>
                </div>
            </div>
        </div>
    )
}
