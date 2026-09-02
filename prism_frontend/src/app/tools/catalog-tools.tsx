"use client"

import { useMemo, useState } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import {
    Loader2,
    Play,
    ChevronDown,
    ChevronUp,
    RefreshCcw,
    Terminal,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

interface CatalogParam {
    type?: string
    description?: string
    default?: any
    items?: { type?: string }
}

interface CatalogTool {
    name: string
    description: string
    category: string
    output_summary?: string
    parameters?: { properties?: Record<string, CatalogParam>; required?: string[] }
}

interface ParamFieldProps {
    key: string
    name: string
    spec: CatalogParam
    value: any
    onChange: (v: any) => void
}

function ParamField({ name, spec, value, onChange }: ParamFieldProps) {
    const base =
        "w-full rounded-lg border border-border/70 bg-black/40 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-accent"
    const type = spec.type || "string"
    const label = `${name}${spec.description ? ` — ${spec.description}` : ""}`
    if (type === "boolean") {
        return (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                    type="checkbox"
                    checked={!!value}
                    onChange={(e) => onChange(e.target.checked)}
                    className="h-4 w-4"
                />
                {label}
            </label>
        )
    }
    if (type === "integer" || type === "number") {
        return (
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span>{label}</span>
                <input
                    type="number"
                    value={value ?? ""}
                    onChange={(e) =>
                        onChange(e.target.value === "" ? undefined : Number(e.target.value))
                    }
                    className={base}
                />
            </label>
        )
    }
    if (type === "array") {
        return (
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                <span>{label}（JSON 数组）</span>
                <textarea
                    rows={2}
                    placeholder='["标签1","标签2"]'
                    value={Array.isArray(value) ? JSON.stringify(value) : (value ?? "")}
                    onChange={(e) => {
                        const raw = e.target.value
                        try {
                            onChange(raw ? JSON.parse(raw) : [])
                        } catch {
                            onChange(raw)
                        }
                    }}
                    className={cn(base, "font-mono resize-none")}
                />
            </label>
        )
    }
    return (
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>{label}</span>
            <input
                type="text"
                value={value ?? ""}
                onChange={(e) => onChange(e.target.value)}
                className={base}
            />
        </label>
    )
}

function CatalogToolCard({ tool }: { tool: CatalogTool }) {
    const { toast } = useToast()
    const [open, setOpen] = useState(false)
    const [values, setValues] = useState<Record<string, any>>({})
    const [result, setResult] = useState<string | null>(null)

    const props = tool.parameters?.properties || {}
    const required = new Set(tool.parameters?.required || [])
    const fieldKeys = Object.keys(props)

    const callMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`/api/v1/tool-catalog/${tool.name}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(values),
            })
            const data = await res.json()
            if (!res.ok) {
                throw new Error(data.detail || `请求失败 ${res.status}`)
            }
            return data
        },
        onSuccess: (data) => {
            setResult(JSON.stringify(data.result, null, 2))
            toast({ title: `「${tool.name}」调用成功` })
        },
        onError: (err: any) => {
            setResult(`错误: ${err.message}`)
            toast({ variant: "destructive", title: "调用失败", description: err.message })
        },
    })

    const missingRequired = [...required].filter((k) => values[k] === undefined || values[k] === "")

    return (
        <Card className="bg-card/40 border-border/70">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div className="flex items-start gap-3">
                    <div className="rounded-lg p-2 border border-border/70 bg-black text-foreground">
                        <Terminal className="h-5 w-5" />
                    </div>
                    <div>
                        <CardTitle className="text-base">{tool.name}</CardTitle>
                        <p className="text-xs text-muted-foreground mt-0.5">{tool.description}</p>
                        {tool.output_summary && (
                            <p className="text-[11px] text-muted-foreground/70 mt-1 leading-relaxed">
                                返回：{tool.output_summary}
                            </p>
                        )}
                    </div>
                </div>
                {tool.category && (
                    <Badge variant="outline" className="bg-black text-white border-white/17 text-xs shrink-0">
                        {tool.category}
                    </Badge>
                )}
            </CardHeader>
            <CardContent>
                <div className="flex items-center gap-2">
                    <Button
                        size="sm"
                        className="h-8 rounded-lg text-xs"
                        onClick={() => setOpen(!open)}
                        variant="secondary"
                    >
                        {open ? <ChevronUp className="mr-1.5 h-3.5 w-3.5" /> : <ChevronDown className="mr-1.5 h-3.5 w-3.5" />}
                        {open ? "收起参数" : "参数"}
                    </Button>
                    <Button
                        size="sm"
                        className="h-8 rounded-lg text-xs"
                        onClick={() => callMutation.mutate()}
                        disabled={callMutation.isPending || (open && missingRequired.length > 0)}
                    >
                        {callMutation.isPending ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <Play className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        调用
                    </Button>
                    {open && missingRequired.length > 0 && (
                        <span className="text-[11px] text-muted-foreground/70">
                            必填：{missingRequired.join(", ")}
                        </span>
                    )}
                </div>

                {open && fieldKeys.length > 0 && (
                    <div className="mt-3 space-y-3 border-t border-border/60 pt-3">
                        {fieldKeys.map((k) => (
                            <ParamField
                                key={k}
                                name={k}
                                spec={props[k]}
                                value={values[k]}
                                onChange={(v) => setValues((prev) => ({ ...prev, [k]: v }))}
                            />
                        ))}
                    </div>
                )}
                {open && fieldKeys.length === 0 && (
                    <p className="mt-3 border-t border-border/60 pt-3 text-xs text-muted-foreground">
                        该工具无参数，直接点「调用」。
                    </p>
                )}

                {result && (
                    <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-border/60 bg-black/40 p-3 text-[11px] font-mono text-foreground whitespace-pre-wrap">
                        {result}
                    </pre>
                )}
            </CardContent>
        </Card>
    )
}

export default function CatalogToolsSection() {
    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ["toolCatalog"],
        queryFn: async () => {
            const res = await fetch("/api/v1/tool-catalog")
            return res.json()
        },
    })

    const tools: CatalogTool[] = useMemo(() => data?.result?.tools || [], [data])

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                    由「声明式工具注册中心」登记，自动同步到 MCP / API / CLI。点"调用"可在线执行真实后端能力。
                </p>
                <Button variant="outline" size="sm" className="rounded-lg text-xs" onClick={() => refetch()}>
                    <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
                    刷新
                </Button>
            </div>

            {isLoading && (
                <div className="py-12 text-center text-muted-foreground text-sm">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                    加载业务工具...
                </div>
            )}
            {isError && (
                <div className="rounded-xl border border-border/70 bg-card/40 py-12 text-center text-muted-foreground">
                    业务工具加载失败，请确认后端 toolkit 已重启、/api/v1/tool-catalog 可用
                </div>
            )}
            {!isLoading && !isError && tools.length === 0 && (
                <div className="rounded-xl border border-border/70 bg-card/40 py-12 text-center text-muted-foreground">
                    暂无业务工具登记
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {tools.map((t) => (
                    <CatalogToolCard key={t.name} tool={t} />
                ))}
            </div>
        </div>
    )
}
