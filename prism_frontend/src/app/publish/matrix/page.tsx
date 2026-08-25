"use client"

import { useState, useMemo, useCallback, useEffect } from "react"
import Image from "next/image"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Save,
  Send,
  Loader2,
  Check,
  RefreshCcw,
  Plus,
  Search,
  Settings,
  Sparkles,
  X,
  ShieldCheck,
  Video,
  Hash,
  AtSign,
  Edit2,
  Trash2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import { Switch } from "@/components/ui/switch"
import { accountsResponseSchema, frontendMaterialsResponseSchema, type Account, type Material } from "@/lib/schemas"
import { fetcher } from "@/lib/api"
import { cn } from "@/lib/utils"
import { DatePicker } from "@/components/ui/date-picker"
import { TimePicker } from "@/components/ui/time-picker"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
// 🆕 NEW: Import new components
import AssignmentStrategySelector from "./components/AssignmentStrategySelector"
import IntervalTimelinePreview from "./components/IntervalTimelinePreview"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { PageHeader } from "@/components/layout/page-scaffold"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PlatformSelector, PlatformKey, PLATFORMS } from "../components/PlatformSelector"
import { DouyinConfig, KuaishouConfig, XhsConfig, BilibiliConfig, VideoChannelConfig } from "../components/PlatformConfigs"
import { MaterialMetadataEditor } from "../components/MaterialMetadataEditor"
import { PlatformMetadataAdapter } from "@/lib/platform-metadata-adapter"
import { backendBaseUrl } from "@/lib/env"

// 平台配置
const PLATFORM_CODE_MAP: Record<PlatformKey, number> = {
  douyin: 3,
  kuaishou: 4,
  xiaohongshu: 1,
  bilibili: 5,
  channels: 2,
  tiktok: 6,
  youtube: 7,
}

type IntervalMode = "account_first" | "video_first"

const INTERVAL_OPTIONS: {
  key: IntervalMode
  title: string
  description: string
  preview: { time: string, slots: string[] }[]
}[] = [
    {
      key: "account_first",
      title: "按账号&视频间隔发布",
      description: "各个账号开始发视频时间不同，多条视频在账号内也做间隔",
      preview: [
        { time: "08:00", slots: ["视频1", "", ""] },
        { time: "08:05", slots: ["", "视频2", ""] },
        { time: "08:10", slots: ["视频4", "", "视频3"] },
        { time: "08:15", slots: ["", "", "视频6"] },
      ]
    },
    {
      key: "video_first",
      title: "按视频间隔发布",
      description: "每个账号按设定时间同时发布，多条视频在账号内按间隔顺序发布",
      preview: [
        { time: "08:00", slots: ["视频1", "视频2", "视频3"] },
        { time: "08:05", slots: ["视频4", "视频5", "视频6"] },
        { time: "08:10", slots: ["视频7", "视频8", "视频9"] },
        { time: "08:15", slots: ["视频10", "视频11", "视频12"] },
      ]
    }
  ]

const PREVIEW_ACCOUNTS = ["A账号", "B账号", "C账号"]
const PREVIEW_COLORS = [
  "bg-emerald-500/15 border-emerald-400/30 text-emerald-100",
  "bg-sky-500/15 border-sky-400/30 text-sky-100",
  "bg-purple-500/15 border-purple-400/30 text-purple-100"
]

interface PublishPlan {
  name: string
  platforms: PlatformKey[]
  accounts: string[]  // account IDs
  materials: string[] // material IDs
  title: string
  tags: string[]
  coverPath?: string // 封面路径
  publishTiming: "immediate" | "scheduled"
  intervalControlEnabled: boolean
  intervalMode: IntervalMode
  scheduleEnabled: boolean
  scheduleDate?: string
  scheduleTime?: string
  videosPerDay: number
  verificationCode?: string // 验证码
  // 🆕 NEW: Assignment strategy fields
  assignmentStrategy: "one_per_account" | "all_per_account" | "cross_platform_all" | "per_platform_custom"
  onePerAccountMode: "random" | "round_robin" | "sequential"
  perPlatformOverrides?: Record<string, string>
  // 🆕 NEW: Deduplication fields
  allowDuplicatePublish: boolean
  dedupWindowDays: number
  // 扩展字段，用于存储各平台特有配置（暂未持久化到后端）
  platformSettings?: Record<string, any>
}

export default function PublishPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isStatusChecking, setIsStatusChecking] = useState(false)
  const [accountSource, setAccountSource] = useState<"internal" | "dispatch">("internal")

  const toBackendFileUrl = useCallback((raw?: string) => {
    if (!raw) return ""
    if (raw.startsWith("http")) return raw
    if (raw.startsWith("/getFile")) return `${backendBaseUrl}${raw}`
    return `${backendBaseUrl}/getFile?filename=${encodeURIComponent(raw)}`
  }, [])

  const handleStatusCheck = async () => {
    setIsStatusChecking(true)
    try {
      const res = await fetch("/api/accounts/deep-sync", { method: "POST" })
      const data = await res.json()
      if (data.success) {
        const stats = data.data
        toast({
          title: "Status check done",
          description: `Checked ${stats?.checked || 0} accounts - Valid ${stats?.valid || 0} - Expired ${stats?.expired || 0}`
        })
        queryClient.invalidateQueries({ queryKey: ["accounts"] })
      } else {
        toast({ title: "Status check failed", description: data.error, variant: "destructive" })
      }
    } catch (e) {
      toast({ title: "Status check error", description: String(e), variant: "destructive" })
    } finally {
      setIsStatusChecking(false)
    }
  }

  const [isMaintaining, setIsMaintaining] = useState(false)

  const handleMaintenance = async () => {
    setIsMaintaining(true)
    try {
      const res = await fetch("/api/accounts/maintenance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}) // 维护所有账号
      })
      const data = await res.json()
      if (data.success) {
        const stats = data.data
        toast({
          title: "维护完成",
          description: `成功: ${stats.success}, 过期: ${stats.expired}, 出错: ${stats.error} `
        })
        queryClient.invalidateQueries({ queryKey: ["accounts"] })
      } else {
        toast({ title: "维护失败", description: data.error, variant: "destructive" })
      }
    } catch (e) {
      toast({ title: "维护出错", description: String(e), variant: "destructive" })
    } finally {
      setIsMaintaining(false)
    }
  }

  // 获取账号和素材
  const { data: accountsData } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => fetcher("/api/accounts?limit=1000", accountsResponseSchema),
    refetchInterval: 10000, // 每10秒自动刷新
  })

  const { data: materialsData } = useQuery({
    queryKey: ["materials"],
    queryFn: () => fetcher("/api/materials", frontendMaterialsResponseSchema),
    refetchInterval: 15000, // 每15秒自动刷新
  })

  const accounts = useMemo(() => {
    if (Array.isArray(accountsData)) return accountsData as Account[]
    if (Array.isArray((accountsData as any)?.data)) return (accountsData as any).data as Account[]
    return []
  }, [accountsData])

  const materials = useMemo(() => {
    const list = Array.isArray((materialsData as any)?.data?.data)
      ? (materialsData as any).data.data
      : Array.isArray((materialsData as any)?.data)
        ? (materialsData as any).data
        : []
    return (list as Material[]).filter((m) => m.status === "pending")
  }, [materialsData])

  // 表单状态
  const [plan, setPlan] = useState<PublishPlan>({
    name: "",
    platforms: [],
    accounts: [],
    materials: [],
    title: "",
    tags: [],
    coverPath: "",
    publishTiming: "immediate",
    intervalControlEnabled: false,
    intervalMode: "account_first",
    scheduleEnabled: false,
    videosPerDay: 1,
    // 🆕 NEW: Assignment strategy defaults
    assignmentStrategy: "all_per_account",
    onePerAccountMode: "random",
    perPlatformOverrides: {},
    // 🆕 NEW: Deduplication defaults
    allowDuplicatePublish: false,
    dedupWindowDays: 7,
    platformSettings: {}
  })

  const [materialPickerOpen, setMaterialPickerOpen] = useState(false)
  const [materialKeyword, setMaterialKeyword] = useState("")
  const [editingMaterialId, setEditingMaterialId] = useState<string | null>(null)
  const [firstFrameById, setFirstFrameById] = useState<Record<string, string>>({})
  const [accountDrawerOpen, setAccountDrawerOpen] = useState(false)
  const [accountSearchKeyword, setAccountSearchKeyword] = useState("")

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 5

  // 账号抽屉分页状态
  const [accountDrawerPage, setAccountDrawerPage] = useState(1)
  const accountDrawerPerPage = 20

  // 素材元数据状态
  interface MaterialMetadata {
    title?: string
    description?: string
    tags?: string[]
    cover_image?: string | null
    // legacy
    coverPath?: string | null
  }

  const ensureFirstFrames = useCallback(async (ids: string[]) => {
    const need = ids.filter((id) => id && !firstFrameById[id])
    if (need.length === 0) return

    // Batch processing with concurrency limit (5 at a time)
    const BATCH_SIZE = 5
    const results: Array<{ id: string; path: string } | null> = []

    for (let i = 0; i < need.length; i += BATCH_SIZE) {
      const batch = need.slice(i, i + BATCH_SIZE)
      try {
        const batchResults = await Promise.all(
          batch.map(async (id) => {
            try {
              const resp = await fetch(`/api/v1/files/${encodeURIComponent(id)}/first-frame`)
              if (!resp.ok) return null
              const data = await resp.json()
              const p = data?.data?.first_frame_path
              return p ? { id, path: String(p) } : null
            } catch {
              return null
            }
          })
        )
        results.push(...batchResults)

        // Update state after each batch for progressive loading
        const batchNext: Record<string, string> = {}
        for (const r of batchResults) {
          if (r?.id && r.path) batchNext[r.id] = r.path
        }
        if (Object.keys(batchNext).length > 0) {
          setFirstFrameById((prev) => ({ ...prev, ...batchNext }))
        }
      } catch {
        // ignore batch error
      }
    }
  }, [firstFrameById])

  useEffect(() => {
    if (plan.materials.length === 0) return
    ensureFirstFrames(plan.materials.map(String))
  }, [plan.materials, ensureFirstFrames])

  useEffect(() => {
    if (!materialPickerOpen) return
    const visible = materials
      .filter((m) => m.filename.toLowerCase().includes(materialKeyword.toLowerCase()))
      .slice(0, 32)
      .map((m) => String(m.id))
    if (visible.length === 0) return
    ensureFirstFrames(visible)
  }, [materialPickerOpen, materialKeyword, materials, ensureFirstFrames])
  const [materialMetadata, setMaterialMetadata] = useState<Record<string, MaterialMetadata>>({})
  const [isGeneratingAI, setIsGeneratingAI] = useState(false)

  const parseTagString = useCallback((raw: any): string[] => {
    if (!raw) return []
    if (Array.isArray(raw)) return raw.map((t) => String(t).trim()).filter(Boolean)
    if (typeof raw !== "string") return []
    const s = raw.trim()
    if (!s) return []
    try {
      const parsed = JSON.parse(s)
      if (Array.isArray(parsed)) return parsed.map((t) => String(t).trim()).filter(Boolean)
    } catch {
      // ignore
    }
    return s
      .split(/[\s,，]+/g)
      .map((t) => t.replace(/^#/, "").trim())
      .filter(Boolean)
  }, [])

  const formatSizeMb = useCallback((value: any): string => {
    const n = typeof value === "number" ? value : Number(String(value || "").replace(/mb$/i, "").trim())
    return Number.isFinite(n) ? n.toFixed(2) : "0.00"
  }, [])

  const formatDuration = useCallback((seconds: any): string => {
    const n = typeof seconds === "number" ? seconds : Number(seconds)
    if (!Number.isFinite(n) || n <= 0) return "-"
    const total = Math.round(n)
    const m = Math.floor(total / 60)
    const s = total % 60
    return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`
  }, [])

  const normalizeTags = useCallback((raw: any): string[] => {
    const items = Array.isArray(raw)
      ? raw.map(tag => String(tag || "").trim())
      : String(raw || "").split(/[\s,，]+/).map(tag => tag.trim())
    const unique: string[] = []
    for (const item of items) {
      const cleaned = item.replace(/^#/, "").trim()
      if (cleaned && !unique.includes(cleaned)) unique.push(cleaned)
    }
    return unique.slice(0, 4)
  }, [])

  // 将 DB 中已有的素材元数据（title/description/tags/cover）注入到编辑态，保证“素材管理/矩阵发布互通”
  useEffect(() => {
    if (!materials || materials.length === 0) return
    setMaterialMetadata((prev) => {
      const next = { ...prev }
      for (const m of materials) {
        const id = String((m as any).id)
        const existing = next[id] || {}
        const coverPath = (m as any).cover_image || (m as any).coverPath
        const title = (m as any).title
        const description = (m as any).description
        const tags = parseTagString((m as any).tags)

        next[id] = {
          ...existing,
          ...(existing.title ? {} : (title ? { title } : {})),
          ...(existing.description ? {} : (description ? { description } : {})),
          ...(existing.tags && existing.tags.length > 0 ? {} : (tags.length > 0 ? { tags } : {})),
          ...(existing.cover_image || existing.coverPath ? {} : (coverPath ? { cover_image: coverPath } : {})),
        }
      }
      return next
    })
  }, [materials, parseTagString])

  // 批量 AI 生成
  const handleBatchAIGenerate = async () => {
    if (selectedMaterialsList.length === 0) {
      toast({ title: "请先选择素材", variant: "destructive" })
      return
    }

    setIsGeneratingAI(true)
    try {
      const promises = selectedMaterialsList.map(async (material) => {
        try {
          const draft = materialMetadata[String(material.id)] || {}
          const titlePrompt = String(draft.title || "").trim()
          const tagsPrompt = (draft.tags && draft.tags.length > 0 ? draft.tags.join(" ") : "").trim()
          const filename = String((material as any).filename || "视频素材")
          const baseName = filename.replace(/\.[^.]+$/, "")
          const response = await fetch("/api/v1/ai/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              messages: [{
                role: "user",
                content: `请基于输入的标题/标签 prompt 优化生成短视频标题与标签（中文优先）；若 prompt 为空，则参考文件名进行二创。\n\n输入：\n- 文件名：${filename}\n- 文件名(去扩展)：${baseName}\n- 标题 prompt：${titlePrompt || "（空）"}\n- 标签 prompt：${tagsPrompt || "（空）"}\n\n要求：\n1) title：不超过30字；若有标题 prompt，保留核心含义并润色；如包含英文词请翻译为中文（专有名词可保留原文并加中文释义）\n2) tags：最多4个字符串数组；不要带#；不要重复；尽量沿用/改编标签 prompt 主题\n3) 只返回严格 JSON（不要markdown），格式：{\"title\":\"...\",\"tags\":[\"...\",...]}\n`
              }],
              stream: false
            })
          })
          const data = await response.json()
          if (data.status === "success" && data.content) {
            let cleanContent = data.content.replace(new RegExp("```json", "g"), "").replace(new RegExp("```", "g"), "").trim()
            if (!cleanContent.startsWith("{")) cleanContent = "{" + cleanContent
            if (!cleanContent.endsWith("}")) cleanContent = cleanContent + "}"

            const json = JSON.parse(cleanContent)
            return {
              id: String(material.id),
              metadata: {
                title: json.title,
                tags: normalizeTags(json.tags)
              }
            }
          }
        } catch (e) {
          console.error(`AI generation failed for ${material.filename}`, e)
        }
        return null
      })

      const results = await Promise.all(promises)

      // 更新 plan 的 title (使用第一个生成的结果)
      if (results.length > 0 && results[0]) {
        setPlan(prev => ({
          ...prev,
          title: results[0]!.metadata.title || prev.title,
          tags: results[0]!.metadata.tags || prev.tags
        }))
      }

      setMaterialMetadata(prev => {
        const next = { ...prev }
        results.forEach(res => {
          if (res) {
            next[res.id] = { ...next[res.id], ...res.metadata }
          }
        })
        return next
      })

      toast({ title: "批量生成完成", description: `成功生成 ${results.filter(Boolean).length} 个素材的元数据` })

    } catch (e) {
      toast({ title: "生成出错", description: String(e), variant: "destructive" })
    } finally {
      setIsGeneratingAI(false)
    }
  }

  // 单个素材 AI 生成
  const handleSingleAIGenerate = async (
    materialId: string,
    prompts?: { titlePrompt?: string; tagsPrompt?: string }
  ) => {
    const material = materials.find(m => String(m.id) === materialId)
    if (!material) return

    try {
      const draft = materialMetadata[String(material.id)] || {}
      const titlePrompt = String(prompts?.titlePrompt || draft.title || "").trim()
      const tagsPrompt = String(prompts?.tagsPrompt || (draft.tags && draft.tags.length > 0 ? draft.tags.join(" ") : "") || "").trim()
      const filename = String((material as any).filename || "视频素材")
      const baseName = filename.replace(/\.[^.]+$/, "")
      const response = await fetch("/api/v1/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{
            role: "user",
            content: `请基于输入的标题/标签 prompt 优化生成短视频标题与标签（中文优先）；若 prompt 为空，则参考文件名进行二创。\n\n输入：\n- 文件名：${filename}\n- 文件名(去扩展)：${baseName}\n- 标题 prompt：${titlePrompt || "（空）"}\n- 标签 prompt：${tagsPrompt || "（空）"}\n\n要求：\n1) title：不超过30字；若有标题 prompt，保留核心含义并润色；如包含英文词请翻译为中文（专有名词可保留原文并加中文释义）\n2) tags：最多4个字符串数组；不要带#；不要重复；尽量沿用/改编标签 prompt 主题\n3) 只返回严格 JSON（不要markdown），格式：{\"title\":\"...\",\"tags\":[\"...\",...]}\n`
          }],
          stream: false
        })
      })

      const data = await response.json()
      if (data.status === "success" && data.content) {
        let cleanContent = data.content.replace(new RegExp("```json", "g"), "").replace(new RegExp("```", "g"), "").trim()
        if (!cleanContent.startsWith("{")) cleanContent = "{" + cleanContent
        if (!cleanContent.endsWith("}")) cleanContent = cleanContent + "}"

        const json = JSON.parse(cleanContent)

        const nextMetadata = {
          title: json.title,
          tags: normalizeTags(json.tags)
        }
        setMaterialMetadata(prev => ({
          ...prev,
          [materialId]: {
            ...prev[materialId],
            ...nextMetadata
          }
        }))

        toast({ title: "生成成功", description: `已为 ${material.filename} 生成元数据` })
        return nextMetadata
      }
    } catch (e) {
      console.error(`AI generation failed for ${material.filename}`, e)
      toast({ title: "生成失败", description: String(e), variant: "destructive" })
    }
    return null
  }

  // 获取账号显示名称 - 与账号管理页面一致，显示真实用户名
  const getAccountDisplayName = (account: Account) =>
    (account.original_name && account.original_name.trim()) ||
    (account.name && !account.name.startsWith("account_") ? account.name : null) ||
    account.user_id ||
    account.id

  const isDispatchAccount = useCallback((account: Account) => {
    const note = (account.note || "").trim().toLowerCase()
    if (!note) return false
    return note.includes("扫码") || note.includes("scan")
  }, [])

  const platformAccounts = useMemo(() => {
    if (plan.platforms.length === 0) return []
    // 显示所有平台匹配的账号，不再过滤状态
    return accounts.filter((acc) =>
      plan.platforms.includes(acc.platform as PlatformKey)
    )
  }, [plan.platforms, accounts])

  const dispatchAccounts = useMemo(
    () => platformAccounts.filter((acc) => isDispatchAccount(acc)),
    [platformAccounts, isDispatchAccount]
  )

  const internalAccounts = useMemo(
    () => platformAccounts.filter((acc) => !isDispatchAccount(acc)),
    [platformAccounts, isDispatchAccount]
  )

  const filteredAccounts = useMemo(
    () => (accountSource === "dispatch" ? dispatchAccounts : internalAccounts),
    [accountSource, dispatchAccounts, internalAccounts]
  )

  // 账号抽屉内的搜索和分页
  const drawerFilteredAccounts = useMemo(() => {
    if (!accountSearchKeyword.trim()) return filteredAccounts
    const keyword = accountSearchKeyword.toLowerCase()
    return filteredAccounts.filter((acc) => {
      const displayName = getAccountDisplayName(acc).toLowerCase()
      const userId = (acc.user_id || "").toLowerCase()
      return displayName.includes(keyword) || userId.includes(keyword)
    })
  }, [filteredAccounts, accountSearchKeyword])

  const drawerPaginatedAccounts = useMemo(() => {
    const startIndex = (accountDrawerPage - 1) * accountDrawerPerPage
    return drawerFilteredAccounts.slice(startIndex, startIndex + accountDrawerPerPage)
  }, [drawerFilteredAccounts, accountDrawerPage, accountDrawerPerPage])

  const totalDrawerPages = Math.ceil(drawerFilteredAccounts.length / accountDrawerPerPage)

  // 当总页数减少且当前页超过总页数时，自动跳转到最后一页
  useMemo(() => {
    if (accountDrawerPage > totalDrawerPages && totalDrawerPages > 0) {
      setAccountDrawerPage(totalDrawerPages)
    }
  }, [totalDrawerPages, accountDrawerPage])

  // 已选账号的显示（主页面预览区）
  const selectedAccountsList = useMemo(() => {
    return accounts.filter(acc => plan.accounts.includes(acc.id))
  }, [accounts, plan.accounts])

  const selectedMaterialsList = useMemo(() => {
    return materials.filter(m => plan.materials.includes(String(m.id)))
  }, [materials, plan.materials])

  // 分页数据
  const paginatedMaterials = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage
    return selectedMaterialsList.slice(startIndex, startIndex + itemsPerPage)
  }, [selectedMaterialsList, currentPage])

  const totalPages = Math.ceil(selectedMaterialsList.length / itemsPerPage)

  // 当总页数减少且当前页超过总页数时，自动跳转到最后一页
  useMemo(() => {
    if (currentPage > totalPages && totalPages > 0) {
      setCurrentPage(totalPages)
    }
  }, [totalPages, currentPage])

  // 切换平台选择
  const togglePlatform = (platform: PlatformKey) => {
    setPlan(prev => ({
      ...prev,
      platforms: prev.platforms.includes(platform)
        ? prev.platforms.filter(p => p !== platform)
        : [...prev.platforms, platform],
      accounts: [], // 切换平台时清空账号选择
    }))
  }

  // 切换账号选择
  const toggleAccount = (accountId: string) => {
    const account = accounts.find(acc => acc.id === accountId)

    if (!account) return

    // 根据 login_status 判断账号是否有效
    const loginStatus = (account as any).login_status || "unknown"
    const platform = account.platform

    // B站特殊处理：无论 login_status 是什么，都默认视为正常（因为使用biliup库）
    let isValidStatus: boolean
    if (platform === "bilibili") {
      isValidStatus = true  // B站账号始终视为有效
    } else {
      isValidStatus = loginStatus === "logged_in"
    }

    // 如果账号登录状态异常，提示用户
    if (!isValidStatus) {
      const statusText = loginStatus === "session_expired" ? "掉线" : "待检测"
      toast({
        title: "账号登录状态异常",
        description: `账号 ${getAccountDisplayName(account)} 的登录状态为"${statusText}"，可能无法正常发布。建议先在账号管理页面重新登录。`,
        variant: "destructive"
      })
      // 仍然允许选择，但给出警告
    }

    setPlan(prev => ({
      ...prev,
      accounts: prev.accounts.includes(accountId)
        ? prev.accounts.filter(id => id !== accountId)
        : [...prev.accounts, accountId],
    }))
  }

  const handlePublishTimingChange = (timing: "immediate" | "scheduled") => {
    if (timing === "immediate") {
      setPlan(prev => ({
        ...prev,
        publishTiming: "immediate",
        scheduleEnabled: false,
        scheduleDate: undefined,
        scheduleTime: undefined,
      }))
      return
    }

    // 选定定时发布时，如果没有设置过时间则默认到最近的整 5 分钟
    const now = new Date()
    const rounded = new Date(now)
    rounded.setMinutes(Math.ceil(now.getMinutes() / 5) * 5 + 5, 0, 0)
    const defaultDate = now.toISOString().split("T")[0]
    const hours = String(rounded.getHours()).padStart(2, "0")
    const minutes = String(rounded.getMinutes()).padStart(2, "0")

    setPlan(prev => ({
      ...prev,
      publishTiming: "scheduled",
      scheduleEnabled: true,
      scheduleDate: prev.scheduleDate || defaultDate,
      scheduleTime: prev.scheduleTime || `${hours}:${minutes}`,
    }))
  }

  const publishMutation = useMutation({
    mutationFn: async () => {
      if (selectedMaterialsList.length === 0) {
        throw new Error("请至少选择一个素材")
      }
      if (plan.accounts.length === 0) {
        throw new Error("请至少选择一个账号")
      }
      if (plan.platforms.length === 0) {
        throw new Error("请选择发布平台")
      }

      // 验证账号平台一致性
      const selectedAccounts = accounts.filter(acc => plan.accounts.includes(acc.id))
      const invalidAccounts = selectedAccounts.filter(
        acc => !plan.platforms.includes(acc.platform as PlatformKey)
      )

      if (invalidAccounts.length > 0) {
        const invalidNames = invalidAccounts.map(acc => getAccountDisplayName(acc)).join(', ')
        toast({
          title: "账号平台不匹配",
          description: `以下账号不属于选中的平台：${invalidNames}`,
          variant: "destructive"
        })
        throw new Error(`账号平台不匹配: ${invalidNames}`)
      }

      // 多平台发布：不指定 platform，让后端自动分组
      const platformCode = plan.platforms.length === 1
        ? PLATFORM_CODE_MAP[plan.platforms[0]]
        : undefined  // 多平台时不指定 platform

      // 构建 items - 使用平台适配器格式化每个素材的元数据
      const items = selectedMaterialsList.map(m => {
        const meta = materialMetadata[m.id]
        // 准备原始元数据
        const rawMetadata = {
          title: meta?.title || plan.title,
          tags: meta?.tags || (plan.tags.length > 0 ? plan.tags : []),
          coverPath: meta?.cover_image || meta?.coverPath || m.cover_image || plan.coverPath || undefined
        }

        // 如果是单平台发布，使用平台适配器格式化
        if (plan.platforms.length === 1) {
          const formatted = PlatformMetadataAdapter.format(plan.platforms[0], rawMetadata)

          return {
            file_id: m.id,
            title: formatted.title || rawMetadata.title,
            description: formatted.combinedContent || "",
            topics: formatted.tags || rawMetadata.tags,
            cover_path: rawMetadata.coverPath
          }
        }

        // 多平台发布时，保留原始格式，让后端根据各自平台处理
        return {
          file_id: m.id,
          title: rawMetadata.title,
          description: "",
          topics: rawMetadata.tags,
          cover_path: rawMetadata.coverPath
        }
      }).filter(item => item.title || item.cover_path)

      // 构建定时时间
      let scheduledTime = undefined
      if (plan.publishTiming === "scheduled" && plan.scheduleDate && plan.scheduleTime) {
        try {
          const date = new Date(plan.scheduleDate)
          const [hours, minutes] = plan.scheduleTime.split(':')
          date.setHours(parseInt(hours), parseInt(minutes))
          // 格式化为 YYYY-MM-DD HH:MM
          const year = date.getFullYear()
          const month = String(date.getMonth() + 1).padStart(2, '0')
          const day = String(date.getDate()).padStart(2, '0')
          const h = String(date.getHours()).padStart(2, '0')
          const m = String(date.getMinutes()).padStart(2, '0')
          scheduledTime = `${year}-${month}-${day} ${h}:${m}`
        } catch (e) {
          console.error("Date parse error", e)
        }
      }

      const payload = {
        file_ids: selectedMaterialsList.map(m => m.id),
        accounts: plan.accounts,
        platform: platformCode,  // 单平台时指定,多平台时为 undefined
        title: plan.title,  // 全局标题,如果为空后端会使用 items 中的信息
        description: "",  // 不再使用描述字段
        topics: plan.tags || [],
        cover_path: plan.coverPath,
        scheduled_time: scheduledTime,
        interval_control_enabled: plan.intervalControlEnabled,
        interval_mode: plan.intervalControlEnabled ? plan.intervalMode : undefined,
        interval_seconds: plan.intervalControlEnabled ? 300 : undefined,
        priority: 5,
        items: items.length > 0 ? items : undefined,  // items 包含每个素材的润色信息
        // 🆕 NEW: Assignment strategy parameters
        assignment_strategy: plan.assignmentStrategy,
        one_per_account_mode: plan.onePerAccountMode,
        per_platform_overrides: plan.perPlatformOverrides,
        // 🆕 NEW: Deduplication parameters
        allow_duplicate_publish: plan.allowDuplicatePublish,
        dedup_window_days: plan.dedupWindowDays,
      }

      // 调试日志
      console.log('📤 发布 Payload:', JSON.stringify(payload, null, 2))
      console.log('📝 Items 数量:', items.length)
      console.log('📝 Plan Title:', plan.title)
      console.log('📝 Material Metadata:', materialMetadata)

      const response = await fetch("/api/v1/publish/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "发布失败")
      }

      return response.json()
    },
    onSuccess: () => {
      toast({ title: "发布成功", description: "任务已提交" })
    },
    onError: (error: any) => {
      toast({ title: "发布失败", description: error?.message || "请稍后再试", variant: "destructive" })
    },
  })

  // 存草稿 - 保存到投放计划
  const savePlanMutation = useMutation({
    mutationFn: async () => {
      // 1. 先创建投放计划
      const planName = plan.title || `矩阵发布_${new Date().toLocaleDateString()}`
      const planResponse = await fetch(`/api/plans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: planName,
          platforms: plan.platforms,
          start_date: plan.scheduleDate || new Date().toISOString().split('T')[0],
          end_date: plan.scheduleDate || new Date().toISOString().split('T')[0],
          goal_type: "matrix_publish",
          remark: plan.tags.join(' ') || "",
          created_by: "matrix_publish"
        }),
      })
      if (!planResponse.ok) throw new Error("创建投放计划失败")
      const planResult = await planResponse.json()
      const planId = planResult.data?.result?.plan_id

      if (!planId) throw new Error("获取计划ID失败")

      const dispatchMode = plan.intervalMode === "video_first" ? "fixed" : "random"
      const now = new Date()
      const today = now.toISOString().split("T")[0]
      const currentTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`
      const timeStrategy = plan.publishTiming === "scheduled" && plan.scheduleDate
        ? {
          mode: "once",
          date: plan.scheduleDate,
          time_points: plan.scheduleTime ? [plan.scheduleTime] : []
        }
        : {
          mode: "once",
          date: today,
          time_points: [currentTime]
        }

      // 2. 为每个平台创建任务包
      for (const platform of plan.platforms) {
        const platformAccounts = plan.accounts.filter(accId => {
          const acc = accounts.find(a => a.id === accId)
          return acc && acc.platform === platform
        })

        if (platformAccounts.length === 0) continue

        await fetch(`/api/task-packages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            plan_id: planId,
            name: `${planName}_${platform}`,
            platform: platform,
            account_ids: platformAccounts,
            material_ids: plan.materials,
            dispatch_mode: dispatchMode,
            time_strategy: timeStrategy,
            created_by: "matrix_publish"
          }),
        })
      }

      return { success: true, plan_id: planId }
    },
    onSuccess: (result) => {
      toast({ title: "保存成功", description: `草稿已保存到投放计划 (ID: ${result.plan_id})` })
      queryClient.invalidateQueries({ queryKey: ["plans"] })
    },
    onError: (error: any) => {
      toast({ title: "保存失败", description: error?.message || "请稍后再试", variant: "destructive" })
    },
  })

  // 渲染平台配置组件
  const renderPlatformConfig = (platform: PlatformKey) => {
    const commonProps = {
      data: plan,
      onChange: (newData: any) => setPlan(prev => ({ ...prev, ...newData }))
    }

    switch (platform) {
      case "douyin": return <DouyinConfig key="douyin" {...commonProps} />
      case "kuaishou": return <KuaishouConfig key="kuaishou" {...commonProps} />
      case "xiaohongshu": return <XhsConfig key="xhs" {...commonProps} />
      case "bilibili": return <BilibiliConfig key="bilibili" {...commonProps} />
      case "channels": return <VideoChannelConfig key="channels" {...commonProps} />
      // TikTok and YouTube both use the shared metadata editor. Their server-side
      // adapters add platform-specific fields such as visibility / playlist.
      case "tiktok":
      case "youtube": return null
      default: return null
    }
  }

  return (
    <div className="space-y-8 px-4 py-4 md:px-6 md:py-6">
      <PageHeader
        title="矩阵发布"
        // description="一键分发内容到多个平台，支持定时、变量、间隔控制"
        actions={
          <div className="flex gap-3">
            {/* <Button
              variant="outline"
              onClick={() => savePlanMutation.mutate()}
              disabled={savePlanMutation.isPending || plan.platforms.length === 0}
              className="border-white/10 bg-white/5 hover:bg-white/10 text-white"
            >
              {savePlanMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              存草稿
            </Button> */}
            <Button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending || plan.platforms.length === 0}
              className="border-white/10 bg-white/5 hover:bg-white/10 text-white"
            >
              {publishMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              立即发布
            </Button>
          </div>
        }
      />

      {/* 1. 平台选择 */}
      <div className="space-y-4">
        <Label className="text-base font-medium">发布渠道</Label>
        <div className="rounded-2xl border border-white/10 bg-black p-5">
          <PlatformSelector
            selected={plan.platforms}
            onSelect={togglePlatform}
          />
        </div>
      </div>

      {/* 2. 通用内容配置 */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium">内容编辑</Label>
          <Button
            variant="outline"
            size="sm"
            className="h-8 border-white/10 bg-white/5 hover:bg-white/10 text-white"
            onClick={() => setMaterialPickerOpen(true)}
          >
            <Plus className="w-3 h-3 mr-2" />
            添加素材
          </Button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black p-6 space-y-6">
          {/* 素材列表 - 分页列表形式 */}
          {selectedMaterialsList.length > 0 ? (
            <div className="space-y-3">
              {paginatedMaterials.map((m, index) => {
                const globalIndex = (currentPage - 1) * itemsPerPage + index
                const metadata = materialMetadata[m.id]
                const hasMetadata = metadata && (metadata.title || (metadata.tags && metadata.tags.length > 0) || metadata.cover_image || metadata.coverPath)

                return (
                  <div
                    key={m.id}
                    className="flex items-start gap-4 p-4 rounded-xl border border-white/10 bg-black/20 hover:bg-black/30 transition-all group"
                  >
                    {/* 序号 */}
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-xs text-white/60 font-medium">
                      {globalIndex + 1}
                    </div>

                    {/* 首帧预览（不叠加 AI 封面） */}
                    <div className="relative w-24 h-32 rounded-lg overflow-hidden border border-white/10 shrink-0 bg-neutral-900">
                      {(() => {
                        const firstFrame = firstFrameById[String(m.id)]
                        if (firstFrame) {
                          return <Image src={toBackendFileUrl(firstFrame)} alt={m.title || m.filename} fill className="object-cover" unoptimized />
                        }
                        return (
                          <div className="w-full h-full flex items-center justify-center">
                            <Video className="w-6 h-6 text-white/20" />
                          </div>
                        )
                      })()}
                      {/* 元数据指示器 */}
                      {hasMetadata && (
                        <div className="absolute top-1 right-1 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full p-0.5">
                          <Sparkles className="w-2.5 h-2.5 text-white" />
                        </div>
                      )}
                    </div>

                    {/* 信息和元数据 */}
                    <div className="flex-1 min-w-0 space-y-3">
                      {/* 文件名 */}
                      <div>
                        <p className="text-sm font-medium text-white truncate">{m.filename}</p>
                        <p className="text-xs text-white/40 mt-0.5">
                          ID: {m.id} · {formatSizeMb((m as any).filesize)}MB · 时长: {formatDuration((m as any).duration)}
                        </p>
                      </div>

                      {/* 元数据预览 */}
                      {hasMetadata ? (
                        <div className="space-y-2">
                          {metadata.title && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-white/40 shrink-0 min-w-[40px]">标题:</span>
                              <p className="text-xs text-white/80 line-clamp-1">{String(metadata.title)}</p>
                            </div>
                          )}
                          {metadata.tags && metadata.tags.length > 0 && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-white/40 shrink-0 min-w-[40px]">标签:</span>
                              <div className="flex flex-wrap gap-1">
                                {metadata.tags.map((tag, i) => (
                                  <Badge key={i} variant="secondary" className="text-[10px] h-5 px-1.5">
                                    #{tag}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          {(metadata.cover_image || metadata.coverPath) && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-white/40 shrink-0 min-w-[40px]">封面:</span>
                              <div className="relative w-16 h-20 rounded border border-white/10 overflow-hidden">
                                <Image src={toBackendFileUrl(metadata.cover_image || metadata.coverPath || "")} alt="封面" fill className="object-cover" unoptimized />
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-white/30 italic">未配置元数据，点击编辑按钮添加</p>
                      )}
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex flex-col gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 border-white/10 hover:bg-white/10"
                        onClick={() => setEditingMaterialId(String(m.id))}
                      >
                        <Edit2 className="w-3 h-3 mr-1.5" />
                        编辑
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                        onClick={() => setPlan(prev => ({ ...prev, materials: prev.materials.filter(id => id !== String(m.id)) }))}
                      >
                        <Trash2 className="w-3 h-3 mr-1.5" />
                        删除
                      </Button>
                    </div>
                  </div>
                )
              })}

              {/* 分页控件 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between py-2 border-t border-white/10">
                  <div className="text-xs text-white/40">
                    第 {currentPage} 页 / 共 {totalPages} 页
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="h-7 text-xs"
                    >
                      上一页
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="h-7 text-xs"
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              )}

              {/* 批量操作提示 */}
              <div className="flex items-center justify-between pt-3 border-t border-white/10">
                <div className="flex items-center gap-2 text-xs text-white/40">
                  <Sparkles className="w-3 h-3" />
                  <span>共 {selectedMaterialsList.length} 个素材</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
                  onClick={handleBatchAIGenerate}
                  disabled={isGeneratingAI}
                >
                  <Sparkles className={cn("w-3 h-3 mr-1.5", isGeneratingAI && "animate-spin")} />
                  {isGeneratingAI ? "批量生成中..." : "批量AI生成"}
                </Button>
              </div>
            </div>
          ) : (
            <div
              className="border-2 border-dashed border-white/10 rounded-xl h-32 flex flex-col items-center justify-center text-white/40 cursor-pointer hover:border-white/20 hover:bg-white/5 transition-all"
              onClick={() => setMaterialPickerOpen(true)}
            >
              <Plus className="w-6 h-6 mb-2" />
              <span>点击添加视频素材</span>
            </div>
          )}

        </div>
      </div>


      {/* 4. 账号选择 */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium">选择账号</Label>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-8 border-white/10 bg-white/5 hover:bg-white/10 text-white"
              onClick={() => setAccountDrawerOpen(true)}
            >
              <Plus className="w-3 h-3 mr-2" />
              选择账号
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black p-5">
          {plan.platforms.length > 0 ? (
            selectedAccountsList.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="text-xs text-white/60">
                    已选 {selectedAccountsList.length} 个账号
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    onClick={() => setPlan(prev => ({ ...prev, accounts: [] }))}
                  >
                    清空
                  </Button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {selectedAccountsList.map(account => {
                    const displayName = getAccountDisplayName(account)
                    return (
                      <div
                        key={account.id}
                        className="flex items-center gap-3 p-3 rounded-xl border border-primary/50 bg-primary/10 relative group"
                      >
                        <div className="relative w-10 h-10 shrink-0">
                          <div className="w-10 h-10 rounded-full bg-neutral-800 flex items-center justify-center border border-white/10 overflow-hidden">
                            {account.avatar ? (
                              <img
                                src={account.avatar}
                                alt={displayName || "Avatar"}
                                className="object-cover w-full h-full"
                                referrerPolicy="no-referrer"
                              />
                            ) : (
                              <span className="text-sm font-medium">{(displayName || "U").slice(0, 1)}</span>
                            )}
                          </div>
                          <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-neutral-900 border border-white/10 flex items-center justify-center p-0.5">
                            <Image
                              src={PLATFORMS.find(p => p.key === (account.platform as any))?.icon ?? "/Tiktok.svg"}
                              alt={account.platform ?? "平台"}
                              width={16}
                              height={16}
                              className="object-contain"
                            />
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium truncate text-primary">
                            {displayName}
                          </div>
                          <div className="text-[10px] text-white/50 truncate">
                            ID: {account.user_id || "未知"}
                          </div>
                        </div>
                        <button
                          onClick={() => toggleAccount(account.id)}
                          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="w-3.5 h-3.5 text-white/50 hover:text-red-400" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : (
              <div
                className="border-2 border-dashed border-white/10 rounded-xl h-32 flex flex-col items-center justify-center text-white/40 cursor-pointer hover:border-white/20 hover:bg-white/5 transition-all"
                onClick={() => setAccountDrawerOpen(true)}
              >
                <Plus className="w-6 h-6 mb-2" />
                <span>点击选择发布账号</span>
              </div>
            )
          ) : (
            <div className="py-12 text-center text-white/40 text-sm border-2 border-dashed border-white/10 rounded-xl">
              请先选择发布平台
            </div>
          )}
        </div>
      </div>

      {/* 🆕 NEW: 4.5 任务分配策略 */}
      {plan.accounts.length > 0 && plan.materials.length > 0 && (
        <AssignmentStrategySelector
          config={{
            assignmentStrategy: plan.assignmentStrategy,
            onePerAccountMode: plan.onePerAccountMode,
            perPlatformOverrides: plan.perPlatformOverrides,
            allowDuplicatePublish: plan.allowDuplicatePublish,
            dedupWindowDays: plan.dedupWindowDays
          }}
          onChange={(config) => setPlan({ ...plan, ...config })}
          videoCount={plan.materials.length}
          accountCount={plan.accounts.length}
        />
      )}

      {/* 5. 发布设置 */}
      <div className="space-y-4">
        <Label className="text-base font-medium">发布设置</Label>
        <div className="rounded-2xl border border-white/10 bg-black p-6 space-y-8">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Label className="text-white/70">发布时间</Label>
                <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-[11px] text-white/70">
                  必选
                </Badge>
              </div>
              <div className="text-xs text-white/50">
                {plan.publishTiming === "immediate" ? "提交后立即触发" : "按设定时间自动发布"}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handlePublishTimingChange("immediate")}
                className={cn(
                  "group rounded-2xl border p-4 text-left transition-all",
                  plan.publishTiming === "immediate"
                    ? "border-primary/50 bg-primary/10 shadow-[0_0_0_1px_rgba(94,234,212,0.2)]"
                    : "border-white/10 bg-white/5 hover:border-white/20"
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "h-4 w-4 rounded-full border",
                      plan.publishTiming === "immediate"
                        ? "border-primary bg-primary/70"
                        : "border-white/30"
                    )}
                  />
                  <div>
                    <div className="font-medium">立即发布</div>
                    <div className="text-xs text-white/60 mt-1">快速发出，适合实时热点</div>
                  </div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handlePublishTimingChange("scheduled")}
                className={cn(
                  "group rounded-2xl border p-4 text-left transition-all",
                  plan.publishTiming === "scheduled"
                    ? "border-primary/50 bg-primary/10 shadow-[0_0_0_1px_rgba(94,234,212,0.2)]"
                    : "border-white/10 bg-black hover:border-white/20"
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "h-4 w-4 rounded-full border",
                      plan.publishTiming === "scheduled"
                        ? "border-primary bg-primary/70"
                        : "border-white/30"
                    )}
                  />
                  <div className="flex flex-col gap-1">
                    <div className="font-medium">定时发布</div>
                    <div className="text-xs text-white/60">设置时间自动发，适合批量排期</div>
                    {plan.scheduleDate && plan.scheduleTime && (
                      <div className="text-[11px] text-primary/90">
                        已设置：{plan.scheduleDate} {plan.scheduleTime}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            </div>

            {plan.publishTiming === "scheduled" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-2">
                <div className="space-y-2">
                  <Label className="text-xs text-white/60">日期</Label>
                  <DatePicker
                    value={plan.scheduleDate}
                    onChange={(date) => setPlan(prev => ({ ...prev, scheduleDate: date }))}
                    placeholder="选择日期"
                    className="w-full"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-white/60">时间</Label>
                  <TimePicker
                    value={plan.scheduleTime}
                    onChange={(time) => setPlan(prev => ({ ...prev, scheduleTime: time }))}
                    className="w-full"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Label className="text-white/70">间隔方式</Label>
                <Badge variant="outline" className="rounded-full border-white/20 bg-white/5 text-[11px] text-white/70">
                  矩阵节奏
                </Badge>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-xs text-white/50 hidden md:block">
                  {plan.intervalControlEnabled ? "选择账号与视频的排布方式" : "关闭状态：默认同时发布"}
                </div>
                <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1.5">
                  <span className="text-xs text-white/70">发布间隔控制</span>
                  <Switch
                    checked={plan.intervalControlEnabled}
                    onCheckedChange={(checked) => setPlan((prev) => ({ ...prev, intervalControlEnabled: checked }))}
                    className="scale-90"
                  />
                </div>
              </div>
            </div>
            {plan.intervalControlEnabled ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {INTERVAL_OPTIONS.map((option) => {
                  const active = plan.intervalMode === option.key
                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => setPlan(prev => ({ ...prev, intervalMode: option.key }))}
                      className={cn(
                        "group rounded-2xl border p-4 text-left transition-all",
                        active
                          ? "border-primary/50 bg-primary/10 shadow-[0_0_0_1px_rgba(94,234,212,0.2)]"
                          : "border-white/10 bg-black hover:border-white/20"
                      )}
                    >
                      <div className="flex items-start gap-3 mb-3">
                        <span
                          className={cn(
                            "mt-1 h-4 w-4 rounded-full border",
                            active ? "border-primary bg-primary/70" : "border-white/30"
                          )}
                        />
                        <div className="space-y-1">
                          <div className="font-medium">{option.title}</div>
                          <div className="text-xs text-white/60 leading-relaxed">{option.description}</div>
                        </div>
                      </div>

                      <div className="rounded-xl border border-white/5 bg-black/20 p-3 space-y-2">
                        <div className="grid grid-cols-[60px_repeat(3,minmax(0,1fr))] gap-2 text-[11px] text-white/60">
                          <div />
                          {PREVIEW_ACCOUNTS.map((name, idx) => (
                            <div key={`${option.key}-account-${idx}`} className="text-center font-medium">
                              {name}
                            </div>
                          ))}
                        </div>
                        <div className="space-y-2">
                          {option.preview.map((row, rowIdx) => (
                            <div
                              key={`${option.key}-row-${rowIdx}`}
                              className="grid grid-cols-[60px_repeat(3,minmax(0,1fr))] gap-2 items-center"
                            >
                              <div className="text-right text-xs text-white/50">{row.time}</div>
                              {row.slots.map((slot, slotIdx) => (
                                <div
                                  key={`${option.key}-slot-${rowIdx}-${slotIdx}`}
                                  className={cn(
                                    "flex h-8 items-center justify-center rounded-lg border border-dashed border-white/10 bg-white/5 text-[11px]",
                                    slot && `${PREVIEW_COLORS[slotIdx % PREVIEW_COLORS.length]} border-solid font-medium`
                                  )}
                                >
                                  {slot && <span>{slot}</span>}
                                </div>
                              ))}
                            </div>
                          ))}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-white/60">
                未开启间隔控制：将按高并发提交任务（同时发布）。如需节奏控制，请开启开关并选择一种排布方式。
              </div>
            )}

            {/* 🆕 NEW: 间隔时间轴预览 */}
            {plan.intervalControlEnabled && (
              <div className="mt-4">
                <IntervalTimelinePreview
                  mode={plan.intervalMode}
                  intervalSeconds={300}
                  randomOffset={0}
                  videoCount={plan.materials.length}
                  accountCount={plan.accounts.length}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Material Picker Dialog */}
      <Dialog open={materialPickerOpen} onOpenChange={setMaterialPickerOpen}>
        <DialogContent className="max-w-3xl bg-neutral-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle>选择素材</DialogTitle>
          </DialogHeader>
          <div className="flex items-center gap-2 mb-4">
            <Search className="w-4 h-4 text-white/50" />
            <Input
              placeholder="搜索素材..."
              className="bg-black/20 border-white/10"
              value={materialKeyword}
              onChange={(e) => setMaterialKeyword(e.target.value)}
            />
          </div>
          <ScrollArea className="h-[400px]">
            <div className="grid grid-cols-4 gap-4">
              {materials
                .filter(m => m.filename.toLowerCase().includes(materialKeyword.toLowerCase()))
                .map(m => {
                  const isSelected = plan.materials.includes(String(m.id))
                  return (
                    <div
                      key={m.id}
                      className={cn(
                        "relative aspect-[3/4] rounded-lg overflow-hidden border cursor-pointer transition-all group",
                        isSelected ? "border-black ring-2 ring-black/50" : "border-white/10 hover:border-white/30"
                      )}
                      onClick={() => {
                        setPlan(prev => ({
                          ...prev,
                          materials: isSelected
                            ? prev.materials.filter(id => id !== String(m.id))
                            : [...prev.materials, String(m.id)]
                        }))
                      }}
                    >
                      {(() => {
                        const firstFrame = firstFrameById[String(m.id)]
                        if (firstFrame) {
                          return <Image src={toBackendFileUrl(firstFrame)} alt={m.title || "Material"} fill className="object-cover" unoptimized />
                        }
                        return (
                          <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
                            <Video className="w-8 h-8 text-white/20" />
                          </div>
                        )
                      })()}
                      <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
                        <p className="text-xs text-white truncate">{m.filename}</p>
                      </div>
                      {isSelected && (
                        <div className="absolute top-2 right-2 bg-black text-white rounded-full p-1">
                          <Check className="w-3 h-3" />
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button onClick={() => setMaterialPickerOpen(false)}>完成</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Material Metadata Editor */}
      {
        editingMaterialId && (() => {
          const material = materials.find(m => String(m.id) === editingMaterialId)
          if (!material) return null

          return (
            <MaterialMetadataEditor
              material={{
                ...material,
                title: material.title || material.filename,
                cover_image: material.cover_image || undefined
              }}
              metadata={materialMetadata[editingMaterialId] || {}}
              selectedPlatforms={plan.platforms}  // 传递选中的平台
              onSave={async (metadata) => {
                // 更新本地状态
                setMaterialMetadata(prev => ({
                  ...prev,
                  [editingMaterialId]: metadata
                }))

                // 保存到后端数据库（与“素材管理”同一张表字段，保证互通）
                try {
                  const payload: Record<string, any> = {}
                  if ("title" in metadata) payload.title = metadata.title
                  if ("description" in metadata) payload.description = metadata.description
                  if ("tags" in metadata) payload.tags = (metadata.tags || []).join(" ")
                  if ("cover_image" in metadata || "coverPath" in metadata) {
                    payload.cover_image = metadata.cover_image ?? metadata.coverPath ?? null
                  }

                  const response = await fetch(`/api/files/${editingMaterialId}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                  })

                  const data = await response.json()

                  if (data.success === false) {
                    throw new Error(data.message || "保存失败")
                  }

                  queryClient.invalidateQueries({ queryKey: ["materials"] })

                  toast({
                    title: "保存成功",
                    description: "素材元数据已保存到数据库"
                  })
                } catch (error: any) {
                  console.error("Failed to save metadata:", error)
                  toast({
                    title: "保存失败",
                    description: error.message,
                    variant: "destructive"
                  })
                }
              }}
              onClose={() => setEditingMaterialId(null)}
              onAIGenerate={handleSingleAIGenerate}
            />
          )
        })()}

      {/* Account Selection Drawer */}
      <Sheet open={accountDrawerOpen} onOpenChange={setAccountDrawerOpen}>
        <SheetContent
          side="right"
          className="w-[95vw] sm:w-[85vw] lg:w-[75vw] xl:w-[1000px] sm:max-w-none bg-neutral-900 border-white/10 text-white overflow-y-auto"
        >
          <SheetHeader>
            <SheetTitle className="text-white">选择账号</SheetTitle>
            <SheetDescription className="text-white/60">
              从 {filteredAccounts.length} 个可用账号中选择发布账号
            </SheetDescription>
          </SheetHeader>

          <div className="mt-6 space-y-4">
            {/* 账号来源切换和搜索 */}
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索账号名称或ID..."
                  className="pl-9 bg-black/20 border-white/10 text-white placeholder:text-white/40"
                  value={accountSearchKeyword}
                  onChange={(e) => {
                    setAccountSearchKeyword(e.target.value)
                    setAccountDrawerPage(1)
                  }}
                />
              </div>
            </div>

            {/* 已选账号统计 */}
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-primary/10 border border-primary/20">
              <div className="text-sm text-white/80">
                已选择 <span className="font-semibold text-primary">{plan.accounts.length}</span> 个账号
              </div>
              {plan.accounts.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                  onClick={() => setPlan(prev => ({ ...prev, accounts: [] }))}
                >
                  全部取消
                </Button>
              )}
            </div>

            {/* 账号表格 */}
            <div className="border border-white/10 rounded-lg overflow-hidden">
              <div className="bg-black/40">
                <div className="grid grid-cols-[40px_60px_1fr_150px_100px_80px_60px] gap-3 px-4 py-3 text-xs font-medium text-white/60 border-b border-white/10">
                  <div className="text-center">#</div>
                  <div>头像</div>
                  <div>账号名称</div>
                  <div>账号ID</div>
                  <div>平台</div>
                  <div className="text-center">状态</div>
                  <div className="text-center">选择</div>
                </div>
              </div>

              {drawerPaginatedAccounts.length > 0 ? (
                <div className="divide-y divide-white/10">
                  {drawerPaginatedAccounts.map((account, index) => {
                    const isSelected = plan.accounts.includes(account.id)
                    const displayName = getAccountDisplayName(account)
                    const globalIndex = (accountDrawerPage - 1) * accountDrawerPerPage + index + 1

                    // 根据 login_status 判断账号是否异常
                    const loginStatus = (account as any).login_status || "unknown"
                    const platform = account.platform

                    // B站特殊处理：无论 login_status 是什么，都默认视为正常（因为使用biliup库）
                    let isValidStatus: boolean
                    let statusText: string
                    let statusVariant: "outline" | "destructive"

                    if (platform === "bilibili") {
                      // B站账号始终显示为正常
                      isValidStatus = true
                      statusText = "正常"
                      statusVariant = "outline"
                    } else {
                      // 其他平台根据 login_status 判断
                      if (loginStatus === "logged_in") {
                        isValidStatus = true
                        statusText = "正常"
                        statusVariant = "outline"
                      } else if (loginStatus === "session_expired") {
                        isValidStatus = false
                        statusText = "掉线"
                        statusVariant = "destructive"
                      } else {
                        isValidStatus = false
                        statusText = "待检测"
                        statusVariant = "outline"
                      }
                    }

                    const isExpired = !isValidStatus

                    return (
                      <div
                        key={account.id}
                        className={cn(
                          "grid grid-cols-[40px_60px_1fr_150px_100px_80px_60px] gap-3 px-4 py-3 items-center hover:bg-white/5 transition-colors cursor-pointer",
                          isSelected && "bg-primary/10",
                          isExpired && "opacity-60"
                        )}
                        onClick={() => toggleAccount(account.id)}
                      >
                        <div className="text-center text-xs text-white/40">
                          {globalIndex}
                        </div>
                        <div className="relative w-10 h-10">
                          <div className={cn(
                            "w-10 h-10 rounded-full bg-neutral-800 flex items-center justify-center border overflow-hidden",
                            isExpired ? "border-red-500/30" : "border-white/10"
                          )}>
                            {account.avatar ? (
                              <img
                                src={account.avatar}
                                alt={displayName || "Avatar"}
                                className="object-cover w-full h-full"
                                referrerPolicy="no-referrer"
                              />
                            ) : (
                              <span className="text-sm font-medium">{(displayName || "U").slice(0, 1)}</span>
                            )}
                          </div>
                          <div className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-neutral-900 border border-white/10 flex items-center justify-center p-0.5">
                            <Image
                              src={PLATFORMS.find(p => p.key === (account.platform as any))?.icon ?? "/Tiktok.svg"}
                              alt={account.platform ?? "平台"}
                              width={12}
                              height={12}
                              className="object-contain"
                            />
                          </div>
                        </div>
                        <div className="min-w-0">
                          <div className={cn(
                            "text-sm font-medium truncate",
                            isSelected ? "text-primary" : isExpired ? "text-white/60" : "text-white"
                          )}>
                            {displayName}
                          </div>
                        </div>
                        <div className={cn("text-xs truncate", isExpired ? "text-white/30" : "text-white/50")}>
                          {account.user_id || "未知"}
                        </div>
                        <div className={cn("text-xs truncate", isExpired ? "text-white/40" : "text-white/60")}>
                          {PLATFORMS.find(p => p.key === account.platform)?.name || account.platform}
                        </div>
                        <div className="flex justify-center">
                          <Badge
                            variant={statusVariant}
                            className={cn(
                              "text-[10px] h-5 px-1.5",
                              statusVariant === "outline" && "bg-green-500/10 border-green-500/30 text-green-400"
                            )}
                          >
                            {statusText}
                          </Badge>
                        </div>
                        <div className="flex justify-center">
                          <div
                            className={cn(
                              "w-5 h-5 rounded border flex items-center justify-center transition-all",
                              isSelected
                                ? "bg-primary border-primary"
                                : "border-white/30 hover:border-white/50"
                            )}
                          >
                            {isSelected && <Check className="w-3 h-3 text-black" />}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="py-12 text-center text-white/40 text-sm">
                  {accountSearchKeyword ? "没有找到匹配的账号" : "暂无可用账号"}
                </div>
              )}
            </div>

            {/* 分页控件 */}
            {totalDrawerPages > 1 && (
              <div className="flex items-center justify-between pt-2">
                <div className="text-xs text-white/50">
                  显示 {(accountDrawerPage - 1) * accountDrawerPerPage + 1} - {Math.min(accountDrawerPage * accountDrawerPerPage, drawerFilteredAccounts.length)} / 共 {drawerFilteredAccounts.length} 个账号
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAccountDrawerPage(p => Math.max(1, p - 1))}
                    disabled={accountDrawerPage === 1}
                    className="h-7 text-xs border-white/10 bg-white/5 hover:bg-white/10"
                  >
                    上一页
                  </Button>
                  <div className="text-xs text-white/60">
                    {accountDrawerPage} / {totalDrawerPages}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setAccountDrawerPage(p => Math.min(totalDrawerPages, p + 1))}
                    disabled={accountDrawerPage === totalDrawerPages}
                    className="h-7 text-xs border-white/10 bg-white/5 hover:bg-white/10"
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}

            {/* 底部操作按钮 */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
              <Button
                variant="ghost"
                onClick={() => setAccountDrawerOpen(false)}
                className="text-white/70 hover:text-white"
              >
                取消
              </Button>
              <Button
                onClick={() => setAccountDrawerOpen(false)}
                className="bg-primary text-black hover:bg-primary/90"
              >
                确定 ({plan.accounts.length})
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
