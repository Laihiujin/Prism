import { useState, useEffect, useMemo } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { format, addDays } from "date-fns"
import { Calendar as CalendarIcon, Loader2, Check, ChevronRight, ChevronLeft, Video, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { useToast } from "@/components/ui/use-toast"

// Types
interface Account {
    account_id: string
    id?: string
    name: string
    platform: string
    avatar?: string
    status?: string
}

interface Material {
    id: string
    filename: string
    url: string
    type: string
    cover_url?: string
}

interface CreateCampaignDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSuccess: () => void
}

const PLATFORMS = [
    { id: "douyin", name: "抖音", color: "bg-black" },
    { id: "kuaishou", name: "快手", color: "bg-orange-500" },
    { id: "xiaohongshu", name: "小红书", color: "bg-red-500" },
    { id: "bilibili", name: "B站", color: "bg-blue-400" },
    { id: "channels", name: "视频号", color: "bg-green-600" },
]

export function CreateCampaignDialog({ open, onOpenChange, onSuccess }: CreateCampaignDialogProps) {
    const { toast } = useToast()
    const [step, setStep] = useState(1)
    const [loading, setLoading] = useState(false)
    const [submitting, setSubmitting] = useState(false)

    // Step 1: Basic Info
    const [name, setName] = useState("")
    const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([])
    const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
    const [goals, setGoals] = useState<string[]>([])
    const [remark, setRemark] = useState("")

    // Step 2: Materials & Schedule
    const [selectedMaterials, setSelectedMaterials] = useState<string[]>([])
    const [scheduleType, setScheduleType] = useState<"immediate" | "range" | "daily">("immediate")
    const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date } | undefined>()

    // 矩阵节奏设置
    const [intervalEnabled, setIntervalEnabled] = useState(false)  // 默认关闭间隔方式
    const [intervalMode, setIntervalMode] = useState<"account_video" | "video">("account_video")
    const [intervalMinutes, setIntervalMinutes] = useState(30)

    // Data
    const [accounts, setAccounts] = useState<Account[]>([])
    const [materials, setMaterials] = useState<Material[]>([])

    // Fetch Data
    useEffect(() => {
        if (open) {
            // Reset form
            setStep(1)
            setName("")
            setSelectedPlatforms([])
            setSelectedAccounts([])
            setSelectedMaterials([])
            setScheduleType("immediate")
            setIntervalEnabled(false)
            setIntervalMode("account_video")
            setIntervalMinutes(30)
            setRemark("")

            fetchAccounts()
            fetchMaterials()
        }
    }, [open])

    const fetchAccounts = async () => {
        try {
            const res = await fetch("/api/v1/accounts/?limit=1000")
            const data = await res.json()
            const items = data.items || data.data || []
            console.log('Fetched accounts:', items.length, items)
            setAccounts(items)
        } catch (e) {
            console.error("Failed to fetch accounts", e)
            toast({ variant: "destructive", title: "获取账号列表失败" })
        }
    }

    const fetchMaterials = async () => {
        try {
            const res = await fetch("/api/v1/files/?limit=100")
            const data = await res.json()
            const items = data.items || []
            // Map backend format to frontend format
            const mappedMaterials = items.map((m: any) => ({
                id: String(m.id),
                filename: m.filename,
                url: m.file_path,
                type: 'video',
                cover_url: m.cover_image
            }))
            console.log('Fetched materials:', mappedMaterials.length, mappedMaterials)
            setMaterials(mappedMaterials)
        } catch (e) {
            console.error("Failed to fetch materials", e)
            toast({ variant: "destructive", title: "获取素材列表失败" })
        }
    }

    // Helper: Get accounts for selected platforms
    const filteredAccounts = useMemo(() => {
        return accounts.filter(acc => selectedPlatforms.includes(acc.platform))
    }, [accounts, selectedPlatforms])

    // Helper: Group filtered accounts by platform
    const accountsByPlatform = useMemo(() => {
        const groups: Record<string, Account[]> = {}
        selectedPlatforms.forEach(p => groups[p] = [])
        filteredAccounts.forEach(acc => {
            if (groups[acc.platform]) groups[acc.platform].push(acc)
        })
        return groups
    }, [filteredAccounts, selectedPlatforms])

    // Helper: Generate Preview Tasks (Simulation)
    const previewTasks = useMemo(() => {
        const tasks: any[] = []
        let taskCount = 0

        // Simple simulation of MatrixScheduler logic (Unique per platform)
        selectedPlatforms.forEach(platform => {
            const platformAccounts = accounts.filter(a => a.platform === platform && selectedAccounts.includes(a.account_id || a.id || ''))
            if (platformAccounts.length === 0) return

            const platformMaterials = [...selectedMaterials] // Copy

            // Round robin assignment
            let accIndex = 0
            platformMaterials.forEach(matId => {
                if (accIndex >= platformAccounts.length) accIndex = 0 // Loop accounts

                const account = platformAccounts[accIndex]
                const material = materials.find(m => m.id === matId)

                tasks.push({
                    id: `preview-${taskCount++}`,
                    platform,
                    account_name: account?.name || account?.account_id,
                    material_name: material?.filename || matId,
                    time: scheduleType === 'immediate' ? '立即发布' : '待定排期',
                    status: '等待生成'
                })

                accIndex++
            })
        })

        return tasks
    }, [selectedPlatforms, selectedAccounts, selectedMaterials, accounts, materials, scheduleType])

    const handleCreate = async (executeNow: boolean) => {
        if (!name) return toast({ variant: "destructive", title: "请输入计划名称" })
        if (selectedPlatforms.length === 0) return toast({ variant: "destructive", title: "请至少选择一个平台" })
        if (selectedAccounts.length === 0) return toast({ variant: "destructive", title: "请至少选择一个账号" })
        if (selectedMaterials.length === 0) return toast({ variant: "destructive", title: "请至少选择一个素材" })

        console.log('Creating campaign:', {
            name,
            platforms: selectedPlatforms,
            accounts: selectedAccounts.length,
            materials: selectedMaterials.length,
            executeNow
        })

        setSubmitting(true)
        try {
            const payload = {
                name,
                platforms: selectedPlatforms,
                account_ids: selectedAccounts,
                material_ids: selectedMaterials,
                schedule_type: scheduleType,
                start_time: dateRange?.from?.toISOString(),
                end_time: dateRange?.to?.toISOString(),
                interval_enabled: intervalEnabled,
                interval_mode: intervalMode,
                interval_minutes: intervalMinutes,
                goals,
                remark,
                execute_now: executeNow
            }

            console.log('Campaign payload:', payload)

            const res = await fetch("/api/v1/campaigns/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })

            const data = await res.json()
            console.log('Campaign response:', data)

            if (data.status === "success") {
                if (executeNow) {
                    const taskCount = data?.result?.tasks_created ?? 0
                    toast({ title: `计划已执行，生成 ${taskCount} 个任务` })
                } else {
                    toast({ title: "预设已保存" })
                }
                onSuccess()
                onOpenChange(false)
            } else {
                toast({ variant: "destructive", title: data.detail || "创建失败" })
            }
        } catch (e) {
            console.error('Campaign create error:', e)
            toast({ variant: "destructive", title: "请求失败，请检查网络连接" })
        } finally {
            setSubmitting(false)
        }
    }

    const togglePlatform = (pid: string) => {
        setSelectedPlatforms(prev =>
            prev.includes(pid) ? prev.filter(p => p !== pid) : [...prev, pid]
        )
    }

    const toggleAccount = (aid: string) => {
        setSelectedAccounts(prev =>
            prev.includes(aid) ? prev.filter(a => a !== aid) : [...prev, aid]
        )
    }

    const toggleMaterial = (mid: string) => {
        setSelectedMaterials(prev =>
            prev.includes(mid) ? prev.filter(m => m !== mid) : [...prev, mid]
        )
    }

    const selectAllAccounts = (platform: string) => {
        const platformAccIds = accounts
            .filter(a => a.platform === platform)
            .map(a => a.account_id || a.id || '')

        const allSelected = platformAccIds.every(id => selectedAccounts.includes(id))

        if (allSelected) {
            // Deselect all
            setSelectedAccounts(prev => prev.filter(id => !platformAccIds.includes(id)))
        } else {
            // Select all
            setSelectedAccounts(prev => [...new Set([...prev, ...platformAccIds])])
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl h-[80vh] flex flex-col p-0 gap-0">
                <DialogHeader className="px-6 py-4 border-b border-gray-800/50">
                    <DialogTitle>新建投放计划</DialogTitle>
                    <DialogDescription>
                        Step {step} of 3: {step === 1 ? "基础信息" : step === 2 ? "素材与排期" : "预览与确认"}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto p-6">
                    {/* Step 1: Basic Info */}
                    {step === 1 && (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <Label>计划名称</Label>
                                <Input
                                    placeholder="例如：12月矩阵投放-双12预热"
                                    value={name}
                                    onChange={e => setName(e.target.value)}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>选择平台</Label>
                                <div className="flex gap-3">
                                    {PLATFORMS.map(p => (
                                        <div
                                            key={p.id}
                                            className={cn(
                                                "flex items-center gap-2 px-4 py-3 rounded-lg border border-gray-800/50 cursor-pointer transition-all",
                                                selectedPlatforms.includes(p.id) ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted"
                                            )}
                                            onClick={() => togglePlatform(p.id)}
                                        >
                                            <div className={cn("w-3 h-3 rounded-full", p.color)} />
                                            <span className="font-medium">{p.name}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {selectedPlatforms.length > 0 && (
                                <div className="space-y-4">
                                    <Label>选择账号</Label>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {selectedPlatforms.map(platform => {
                                            const pInfo = PLATFORMS.find(p => p.id === platform)
                                            const accs = accountsByPlatform[platform] || []

                                            return (
                                                <Card key={platform} className="overflow-hidden border-gray-800">
                                                    <div className="px-3 py-2 bg-black border-b border-gray-800/50 flex justify-between items-center">
                                                        <div className="flex items-center gap-2">
                                                            <div className={cn("w-2 h-2 rounded-full", pInfo?.color)} />
                                                            <span className="font-medium text-sm">{pInfo?.name}</span>
                                                            <Badge variant="secondary" className="text-xs">{accs.length}</Badge>
                                                        </div>
                                                        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => selectAllAccounts(platform)}>
                                                            全选
                                                        </Button>
                                                    </div>
                                                    <ScrollArea className="h-[150px] p-2">
                                                        {accs.length === 0 ? (
                                                            <div className="text-center text-muted-foreground text-sm py-4">无可用账号</div>
                                                        ) : (
                                                            <div className="space-y-1">
                                                                {accs.map(acc => (
                                                                    <div
                                                                        key={acc.account_id || acc.id}
                                                                        className="flex items-center gap-2 p-2 hover:bg-muted rounded cursor-pointer"
                                                                        onClick={() => toggleAccount(acc.account_id || acc.id || '')}
                                                                    >
                                                                        <Checkbox
                                                                            checked={selectedAccounts.includes(acc.account_id || acc.id || '')}
                                                                            onCheckedChange={() => toggleAccount(acc.account_id || acc.id || '')}
                                                                        />
                                                                        <div className="flex items-center gap-2 overflow-hidden">
                                                                            <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center shrink-0">
                                                                                {acc.avatar ? <img src={acc.avatar} className="w-full h-full rounded-full" /> : <User className="w-3 h-3" />}
                                                                            </div>
                                                                            <span className="text-sm truncate">{acc.name}</span>
                                                                        </div>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </ScrollArea>
                                                </Card>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}

                            <div className="space-y-2">
                                <Label>投放目标</Label>
                                <div className="flex gap-2">
                                    {['曝光', '涨粉', '引流', '转化'].map(g => (
                                        <Badge
                                            key={g}
                                            variant={goals.includes(g) ? "default" : "outline"}
                                            className="cursor-pointer px-3 py-1"
                                            onClick={() => setGoals(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g])}
                                        >
                                            {g}
                                        </Badge>
                                    ))}
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label>备注</Label>
                                <Textarea
                                    placeholder="可选备注信息..."
                                    value={remark}
                                    onChange={e => setRemark(e.target.value)}
                                />
                            </div>
                        </div>
                    )}

                    {/* Step 2: Materials & Schedule */}
                    {step === 2 && (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <Label>选择素材 ({selectedMaterials.length})</Label>
                                    <Button variant="outline" size="sm" onClick={() => setSelectedMaterials(materials.map(m => m.id))}>全选</Button>
                                </div>
                                <ScrollArea className="h-[400px] border border-gray-800/50 rounded-md p-4">
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        {materials.map(m => (
                                            <div
                                                key={m.id}
                                                className={cn(
                                                    "relative aspect-video rounded-lg border border-gray-800/50 overflow-hidden cursor-pointer group",
                                                    selectedMaterials.includes(m.id) ? "ring-2 ring-primary border-primary" : "hover:border-gray-800"
                                                )}
                                                onClick={() => toggleMaterial(m.id)}
                                            >
                                                {m.cover_url ? (
                                                    <img src={m.cover_url} className="w-full h-full object-cover" />
                                                ) : (
                                                    <div className="w-full h-full bg-muted flex items-center justify-center">
                                                        <Video className="w-8 h-8 text-muted-foreground" />
                                                    </div>
                                                )}
                                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                                    {selectedMaterials.includes(m.id) && <Check className="w-8 h-8 text-white" />}
                                                </div>
                                                <div className="absolute bottom-0 left-0 right-0 p-2 bg-black/60 text-white text-xs truncate">
                                                    {m.filename}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </ScrollArea>
                            </div>

                            <div className="space-y-4">
                                <Label>排期设置</Label>
                                <div className="grid grid-cols-3 gap-4">
                                    <div
                                        className={cn("border border-gray-800/50 rounded-lg p-4 cursor-pointer text-center hover:bg-muted", scheduleType === 'immediate' && "border-primary bg-primary/5")}
                                        onClick={() => setScheduleType('immediate')}
                                    >
                                        <div className="font-medium">立即执行</div>
                                        <div className="text-xs text-muted-foreground mt-1">生成任务后立即进入队列</div>
                                    </div>
                                    <div
                                        className={cn("border border-gray-800/50 rounded-lg p-4 cursor-pointer text-center hover:bg-muted", scheduleType === 'range' && "border-primary bg-primary/5")}
                                        onClick={() => setScheduleType('range')}
                                    >
                                        <div className="font-medium">固定区间</div>
                                        <div className="text-xs text-muted-foreground mt-1">在指定日期范围内分发</div>
                                    </div>
                                    <div
                                        className={cn("border border-gray-800/50 rounded-lg p-4 cursor-pointer text-center hover:bg-muted", scheduleType === 'daily' && "border-primary bg-primary/5")}
                                        onClick={() => setScheduleType('daily')}
                                    >
                                        <div className="font-medium">每日定量</div>
                                        <div className="text-xs text-muted-foreground mt-1">每天固定发布 N 条</div>
                                    </div>
                                </div>

                                {scheduleType !== 'immediate' && (
                                    <div className="space-y-4">
                                        <div className="p-4 border border-gray-800/50 rounded-lg bg-black">
                                            <div className="flex items-center justify-between mb-3">
                                                <div>
                                                    <Label className="font-medium">矩阵节奏</Label>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {intervalEnabled ? "已启用间隔发布" : "关闭时所有任务将同时发布"}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Label htmlFor="interval-toggle" className="text-sm cursor-pointer">
                                                        {intervalEnabled ? "已启用" : "已关闭"}
                                                    </Label>
                                                    <input
                                                        id="interval-toggle"
                                                        type="checkbox"
                                                        checked={intervalEnabled}
                                                        onChange={(e) => setIntervalEnabled(e.target.checked)}
                                                        className="toggle toggle-primary w-12 h-6"
                                                        style={{
                                                            appearance: 'none',
                                                            width: '3rem',
                                                            height: '1.5rem',
                                                            borderRadius: '9999px',
                                                            backgroundColor: intervalEnabled ? 'hsl(var(--primary))' : 'hsl(var(--muted))',
                                                            position: 'relative',
                                                            cursor: 'pointer',
                                                            transition: 'background-color 0.2s',
                                                        }}
                                                    />
                                                </div>
                                            </div>

                                            {intervalEnabled && (
                                                <div className="space-y-3 pt-3 border-t border-gray-800/50">
                                                    <div className="grid grid-cols-2 gap-3">
                                                        <div
                                                            className={cn(
                                                                "border border-gray-800/50 rounded-lg p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                                                                intervalMode === 'account_video' && "border-primary bg-primary/10 ring-1 ring-primary"
                                                            )}
                                                            onClick={() => setIntervalMode('account_video')}
                                                        >
                                                            <div className="font-medium text-sm mb-1">按账号&视频间隔</div>
                                                            <div className="text-xs text-muted-foreground">各账号开始时间不同，视频在账号内间隔发布</div>
                                                        </div>
                                                        <div
                                                            className={cn(
                                                                "border border-gray-800/50 rounded-lg p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                                                                intervalMode === 'video' && "border-primary bg-primary/10 ring-1 ring-primary"
                                                            )}
                                                            onClick={() => setIntervalMode('video')}
                                                        >
                                                            <div className="font-medium text-sm mb-1">按视频间隔</div>
                                                            <div className="text-xs text-muted-foreground">各账号同时开始，视频在账号内按间隔发布</div>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-3">
                                                        <Label className="text-sm whitespace-nowrap">间隔时长</Label>
                                                        <div className="flex items-center gap-2">
                                                            <Input
                                                                type="number"
                                                                min="1"
                                                                max="1440"
                                                                value={intervalMinutes}
                                                                onChange={(e) => setIntervalMinutes(parseInt(e.target.value) || 30)}
                                                                className="w-24 bg-black/5 border-gray-800/50"
                                                            />
                                                            <span className="text-sm text-muted-foreground">分钟</span>
                                                        </div>
                                                        <span className="text-xs text-muted-foreground ml-auto">
                                                            = {Math.floor(intervalMinutes / 60)}h {intervalMinutes % 60}m
                                                        </span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                        <div className="p-4 border border-gray-800/50 rounded-lg bg-black">
                                            <Label className="mb-2 block">选择日期范围</Label>
                                            <Popover>
                                                <PopoverTrigger asChild>
                                                    <Button
                                                        id="date"
                                                        variant={"outline"}
                                                        className={cn(
                                                            "w-[300px] justify-start text-left font-normal",
                                                            !dateRange && "text-muted-foreground"
                                                        )}
                                                    >
                                                        <CalendarIcon className="mr-2 h-4 w-4" />
                                                        {dateRange?.from ? (
                                                            dateRange.to ? (
                                                                <>
                                                                    {format(dateRange.from, "LLL dd, y")} -{" "}
                                                                    {format(dateRange.to, "LLL dd, y")}
                                                                </>
                                                            ) : (
                                                                format(dateRange.from, "LLL dd, y")
                                                            )
                                                        ) : (
                                                            <span>Pick a date</span>
                                                        )}
                                                    </Button>
                                                </PopoverTrigger>
                                                <PopoverContent className="w-auto p-0" align="start">
                                                    <Calendar
                                                        initialFocus
                                                        mode="range"
                                                        defaultMonth={dateRange?.from}
                                                        selected={dateRange as any}
                                                        onSelect={setDateRange as any}
                                                        numberOfMonths={2}
                                                    />
                                                </PopoverContent>
                                            </Popover>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Step 3: Preview */}
                    {step === 3 && (
                        <div className="space-y-6">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card className="border-gray-800/50">
                                    <CardContent className="pt-6 text-center">
                                        <div className="text-2xl font-bold">{selectedPlatforms.length}</div>
                                        <div className="text-xs text-muted-foreground">覆盖平台</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-gray-800/50">
                                    <CardContent className="pt-6 text-center">
                                        <div className="text-2xl font-bold">{selectedAccounts.length}</div>
                                        <div className="text-xs text-muted-foreground">使用账号</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-gray-800/50">
                                    <CardContent className="pt-6 text-center">
                                        <div className="text-2xl font-bold">{selectedMaterials.length}</div>
                                        <div className="text-xs text-muted-foreground">素材数量</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-gray-800/50">
                                    <CardContent className="pt-6 text-center">
                                        <div className="text-2xl font-bold text-primary">{previewTasks.length}</div>
                                        <div className="text-xs text-muted-foreground">预计生成任务</div>
                                    </CardContent>
                                </Card>
                            </div>

                            <div className="border border-gray-800/50 rounded-md">
                                <div className="bg-black border-b border-gray-800/50 px-4 py-2 text-sm font-medium grid grid-cols-5 gap-4">
                                    <div>平台</div>
                                    <div>账号</div>
                                    <div className="col-span-2">素材</div>
                                    <div>状态</div>
                                </div>
                                <ScrollArea className="h-[300px]">
                                    {previewTasks.map((task, i) => (
                                        <div key={i} className="px-4 py-3 text-sm grid grid-cols-5 gap-4 border-b border-gray-800/30 last:border-0 hover:bg-muted/50">
                                            <div className="flex items-center gap-2">
                                                <div className={cn("w-2 h-2 rounded-full", PLATFORMS.find(p => p.id === task.platform)?.color)} />
                                                {PLATFORMS.find(p => p.id === task.platform)?.name}
                                            </div>
                                            <div className="truncate">{task.account_name}</div>
                                            <div className="col-span-2 truncate">{task.material_name}</div>
                                            <div>
                                                <Badge variant="outline">{task.status}</Badge>
                                            </div>
                                        </div>
                                    ))}
                                </ScrollArea>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="px-6 py-4 border-t bg-black border-gray-800/50">
                    {step > 1 && (
                        <Button variant="outline" onClick={() => setStep(step - 1)} disabled={submitting}>
                            <ChevronLeft className="w-4 h-4 mr-2" /> 上一步
                        </Button>
                    )}
                    {step < 3 ? (
                        <Button onClick={() => setStep(step + 1)}>
                            下一步 <ChevronRight className="w-4 h-4 ml-2" />
                        </Button>
                    ) : (
                        <div className="flex items-center gap-2">
                            <Button variant="outline" onClick={() => handleCreate(false)} disabled={submitting}>
                                保存预设
                            </Button>
                            <Button onClick={() => handleCreate(true)} disabled={submitting}>
                                {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                立即执行
                            </Button>
                        </div>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
