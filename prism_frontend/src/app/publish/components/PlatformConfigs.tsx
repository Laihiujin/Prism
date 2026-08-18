import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Link, Gamepad2, Smartphone, Store, FileText } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

interface ConfigProps {
    data: any
    onChange: (data: any) => void
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
                <Button variant="outline" className="w-full justify-start text-white/50 border-white/10 bg-black/20 h-9 hover:bg-white/5 hover:text-white">
                    <Gamepad2 className="w-3 h-3 mr-2" />
                    <span className="text-xs">选择小程序/游戏/应用</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#0A0A0A] border-white/10 text-white max-w-2xl">
                <DialogHeader>
                    <DialogTitle>选择挂载内容</DialogTitle>
                </DialogHeader>

                {/* 标签页 */}
                <div className="flex gap-2 border-b border-white/10 pb-2">
                    {tabs.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={cn(
                                "px-3 py-1 text-xs rounded-md transition-all",
                                activeTab === tab.key
                                    ? "bg-white text-black"
                                    : "text-white/60 hover:text-white hover:bg-white/5"
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
                    className="bg-black/20 border-white/10"
                />
                <ScrollArea className="h-[400px]">
                    <div className="grid grid-cols-2 gap-3">
                        {filteredItems.map(item => (
                            <div
                                key={item.id}
                                onClick={() => {
                                    onSelect(item)
                                }}
                                className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black hover:bg-white/10 cursor-pointer transition-all"
                            >
                                <span className="text-2xl">{item.icon}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium truncate">{item.name}</div>
                                    <div className="text-xs text-white/50 truncate">{item.description || item.type}</div>
                                </div>
                                <Badge variant="outline" className="text-[10px] shrink-0 border-white/20">
                                    {item.type}
                                </Badge>
                            </div>
                        ))}
                        {filteredItems.length === 0 && (
                            <div className="col-span-2 text-center py-8 text-white/40">
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

    const pois = [
        { id: 1, name: "北京三里屯", address: "朝阳区三里屯路", distance: "1.2km" },
        { id: 2, name: "上海外滩", address: "黄浦区中山东一路", distance: "3.5km" },
        { id: 3, name: "广州塔", address: "海珠区阅江西路", distance: "5.8km" },
    ]

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-white/50 border-white/10 bg-black/20 h-9 hover:bg-white/5 hover:text-white">
                    <MapPin className="w-3 h-3 mr-2" />
                    <span className="text-xs">添加位置信息</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#0A0A0A] border-white/10 text-white">
                <DialogHeader>
                    <DialogTitle>选择地点</DialogTitle>
                </DialogHeader>
                <Input
                    placeholder="搜索地点..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-black/20 border-white/10"
                />
                <ScrollArea className="h-[300px]">
                    <div className="space-y-2">
                        {pois
                            .filter(poi => poi.name.toLowerCase().includes(search.toLowerCase()))
                            .map(poi => (
                                <div
                                    key={poi.id}
                                    onClick={() => onSelect(poi)}
                                    className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black hover:bg-white/10 cursor-pointer transition-all"
                                >
                                    <MapPin className="w-5 h-5 text-primary" />
                                    <div className="flex-1">
                                        <div className="text-sm font-medium">{poi.name}</div>
                                        <div className="text-xs text-white/50">{poi.address} · {poi.distance}</div>
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
    const [selectedMiniProgram, setSelectedMiniProgram] = useState<MountableItem | null>(null)
    const [selectedPOI, setSelectedPOI] = useState<any>(null)

    return (
        <div className="space-y-4 p-5 bg-black rounded-2xl border border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">抖音配置</h3>
                <Badge variant="outline" className="text-[10px] border-blue-500/30 text-blue-400">抖音</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载小程序/游戏/应用 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载内容
                    </Label>
                    <MiniProgramDialog onSelect={setSelectedMiniProgram} platform="douyin" />
                    {selectedMiniProgram && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/30">
                            <span className="text-2xl">{selectedMiniProgram.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-white">{selectedMiniProgram.name}</div>
                                <div className="text-[10px] text-white/50">{selectedMiniProgram.description}</div>
                            </div>
                            <Badge variant="outline" className="text-[10px] shrink-0 border-blue-400/50 text-blue-400">
                                {selectedMiniProgram.type}
                            </Badge>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10 shrink-0"
                                onClick={() => setSelectedMiniProgram(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        添加地点
                    </Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30">
                            <MapPin className="w-4 h-4 text-green-400" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-white truncate">{selectedPOI.name}</div>
                                <div className="text-[10px] text-white/50 truncate">{selectedPOI.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10"
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

export function KuaishouConfig({ data, onChange }: ConfigProps) {
    const [selectedGame, setSelectedGame] = useState<MountableItem | null>(null)
    const [selectedPOI, setSelectedPOI] = useState<any>(null)

    return (
        <div className="space-y-4 p-5 bg-black rounded-2xl border border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">快手配置</h3>
                <Badge variant="outline" className="text-[10px] border-orange-500/30 text-orange-400">快手</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载游戏/应用 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载游戏或应用
                    </Label>
                    <MiniProgramDialog onSelect={setSelectedGame} platform="kuaishou" />
                    {selectedGame && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-orange-500/10 to-red-500/10 border border-orange-500/30">
                            <span className="text-2xl">{selectedGame.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-white">{selectedGame.name}</div>
                                <div className="text-[10px] text-white/50">{selectedGame.description}</div>
                            </div>
                            <Badge variant="outline" className="text-[10px] shrink-0 border-orange-400/50 text-orange-400">
                                {selectedGame.type}
                            </Badge>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10 shrink-0"
                                onClick={() => setSelectedGame(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        添加地点
                    </Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30">
                            <MapPin className="w-4 h-4 text-green-400" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-white truncate">{selectedPOI.name}</div>
                                <div className="text-[10px] text-white/50 truncate">{selectedPOI.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10"
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
    const [selectedPOI, setSelectedPOI] = useState<any>(null)

    return (
        <div className="space-y-4 p-5 bg-black rounded-2xl border border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">小红书配置</h3>
                <Badge variant="outline" className="text-[10px] border-red-500/30 text-red-400">小红书</Badge>
            </div>

            <div className="grid gap-4">
                {/* 添加地点 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60">添加地点</Label>
                    <POIDialog onSelect={setSelectedPOI} />
                    {selectedPOI && (
                        <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/30">
                            <MapPin className="w-4 h-4 text-primary" />
                            <span className="text-xs text-white truncate">{selectedPOI.name}</span>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="ml-auto h-6 w-6 p-0 hover:bg-white/10"
                                onClick={() => setSelectedPOI(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 话题标签 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60">话题标签</Label>
                    <Input
                        placeholder="输入话题，用空格分隔"
                        className="bg-black/20 border-white/10 text-xs"
                    />
                    <p className="text-[10px] text-white/40">例如：#美食 #探店 #生活分享</p>
                </div>
            </div>
        </div>
    )
}

export function BilibiliConfig({ data, onChange }: ConfigProps) {
    const [selectedGame, setSelectedGame] = useState<MountableItem | null>(null)

    // B站专属游戏列表
    const bilibiliGames: MountableItem[] = [
        { id: 101, name: "原神", type: "游戏", icon: "⚔️", description: "开放世界冒险游戏" },
        { id: 102, name: "英雄联盟", type: "游戏", icon: "🎮", description: "MOBA竞技游戏" },
        { id: 103, name: "王者荣耀", type: "游戏", icon: "👑", description: "移动端MOBA" },
        { id: 104, name: "我的世界", type: "游戏", icon: "🧱", description: "沙盒建造游戏" },
        { id: 105, name: "崩坏：星穹铁道", type: "游戏", icon: "🚂", description: "回合制RPG" },
    ]

    return (
        <div className="space-y-4 p-5 bg-black rounded-2xl border border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">B站配置</h3>
                <Badge variant="outline" className="text-[10px] border-pink-500/30 text-pink-400">B站</Badge>
            </div>

            <div className="space-y-4">
                {/* 挂载游戏 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <Gamepad2 className="w-3 h-3" />
                        挂载游戏
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-white/50 border-white/10 bg-black/20 h-9 hover:bg-white/5 hover:text-white">
                                <Gamepad2 className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择游戏</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0A0A0A] border-white/10 text-white max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择游戏</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="grid grid-cols-2 gap-3">
                                    {bilibiliGames.map(game => (
                                        <div
                                            key={game.id}
                                            onClick={() => setSelectedGame(game)}
                                            className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black hover:bg-white/10 cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{game.icon}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{game.name}</div>
                                                <div className="text-xs text-white/50 truncate">{game.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedGame && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-pink-500/10 to-purple-500/10 border border-pink-500/30">
                            <span className="text-2xl">{selectedGame.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-white">{selectedGame.name}</div>
                                <div className="text-[10px] text-white/50">{selectedGame.description}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10 shrink-0"
                                onClick={() => setSelectedGame(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 分区选择 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60">分区</Label>
                    <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary" className="cursor-pointer">生活</Badge>
                        <Badge variant="outline" className="cursor-pointer border-white/10 text-white/60 hover:bg-white/10">游戏</Badge>
                        <Badge variant="outline" className="cursor-pointer border-white/10 text-white/60 hover:bg-white/10">娱乐</Badge>
                        <Badge variant="outline" className="cursor-pointer border-white/10 text-white/60 hover:bg-white/10">知识</Badge>
                        <Badge variant="outline" className="cursor-pointer border-white/10 text-white/60 hover:bg-white/10">科技</Badge>
                    </div>
                </div>

                {/* 标签 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60">标签</Label>
                    <Input
                        placeholder="按回车键输入标签"
                        className="bg-black/20 border-white/10 text-xs"
                        value={data.tags ? (Array.isArray(data.tags) ? data.tags.join(' ') : data.tags) : ""}
                        onChange={(e) => onChange({ ...data, tags: e.target.value.split(' ') })}
                    />
                    <p className="text-[10px] text-white/40">使用空格分隔多个标签</p>
                </div>
            </div>
        </div>
    )
}

export function VideoChannelConfig({ data, onChange }: ConfigProps) {
    const [selectedArticle, setSelectedArticle] = useState<any>(null)
    const [selectedMiniProgram, setSelectedMiniProgram] = useState<MountableItem | null>(null)
    const [selectedLocation, setSelectedLocation] = useState<any>(null)

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
        <div className="space-y-4 p-5 bg-black rounded-2xl border border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white/80">视频号配置</h3>
                <Badge variant="outline" className="text-[10px] border-green-500/30 text-green-400">视频号</Badge>
            </div>

            <div className="grid gap-4">
                {/* 挂载公众号文章 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        挂载公众号文章
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-white/50 border-white/10 bg-black/20 h-9 hover:bg-white/5 hover:text-white">
                                <FileText className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择公众号文章</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0A0A0A] border-white/10 text-white max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择公众号文章</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="space-y-2">
                                    {articles.map(article => (
                                        <div
                                            key={article.id}
                                            onClick={() => setSelectedArticle(article)}
                                            className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black hover:bg-white/10 cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{article.cover}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{article.title}</div>
                                                <div className="text-xs text-white/50">{article.date}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedArticle && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30">
                            <FileText className="w-4 h-4 text-green-400" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-white truncate">{selectedArticle.title}</div>
                                <div className="text-[10px] text-white/50">{selectedArticle.date}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10 shrink-0"
                                onClick={() => setSelectedArticle(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 挂载小程序 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <Smartphone className="w-3 h-3" />
                        挂载小程序
                    </Label>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="w-full justify-start text-white/50 border-white/10 bg-black/20 h-9 hover:bg-white/5 hover:text-white">
                                <Smartphone className="w-3 h-3 mr-2" />
                                <span className="text-xs">选择小程序</span>
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0A0A0A] border-white/10 text-white max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>选择小程序</DialogTitle>
                            </DialogHeader>
                            <ScrollArea className="h-[400px]">
                                <div className="grid grid-cols-2 gap-3">
                                    {wechatMiniPrograms.map(mini => (
                                        <div
                                            key={mini.id}
                                            onClick={() => setSelectedMiniProgram(mini)}
                                            className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-black hover:bg-white/10 cursor-pointer transition-all"
                                        >
                                            <span className="text-2xl">{mini.icon}</span>
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{mini.name}</div>
                                                <div className="text-xs text-white/50 truncate">{mini.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </DialogContent>
                    </Dialog>
                    {selectedMiniProgram && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/30">
                            <span className="text-2xl">{selectedMiniProgram.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-white">{selectedMiniProgram.name}</div>
                                <div className="text-[10px] text-white/50">{selectedMiniProgram.description}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10 shrink-0"
                                onClick={() => setSelectedMiniProgram(null)}
                            >
                                ×
                            </Button>
                        </div>
                    )}
                </div>

                {/* 所在位置 */}
                <div className="space-y-2">
                    <Label className="text-xs text-white/60 flex items-center gap-2">
                        <MapPin className="w-3 h-3" />
                        所在位置
                    </Label>
                    <POIDialog onSelect={setSelectedLocation} />
                    {selectedLocation && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30">
                            <MapPin className="w-4 h-4 text-green-400" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs text-white truncate">{selectedLocation.name}</div>
                                <div className="text-[10px] text-white/50 truncate">{selectedLocation.address}</div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 w-6 p-0 hover:bg-white/10"
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
