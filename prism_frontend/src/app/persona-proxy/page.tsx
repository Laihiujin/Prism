"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, RefreshCw, Server, ShieldCheck, CheckCircle2, XCircle } from "lucide-react"
import { PageHeader, PageSection } from "@/components/layout/page-scaffold"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/components/ui/use-toast"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface GatewayStatus {
  subscription_url: string
  mapping: Record<string, string>
  updated_at: string
  ports: Record<string, boolean>
  controller_ok: boolean
  regions: Record<string, { port: number; name: string }>
}

// 固定展示顺序与完整地区名
const REGION_ORDER: { key: string; name: string; flag: string }[] = [
  { key: "sg", name: "新加坡", flag: "🇸🇬" },
  { key: "jp", name: "日本", flag: "🇯🇵" },
  { key: "us", name: "美国", flag: "🇺🇸" },
  { key: "de", name: "德国", flag: "🇩🇪" },
  { key: "tw", name: "台湾", flag: "🇹🇼" },
  { key: "hk", name: "香港", flag: "🇭🇰" },
]

async function jsonFetch<T = any>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = body?.detail || body?.message || `HTTP ${res.status}`
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail))
  }
  return body
}

export default function PersonaProxyPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [url, setUrl] = useState("")

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["persona-proxy-status"],
    queryFn: () => jsonFetch<any>("/api/v1/persona-proxy"),
    refetchInterval: 15000,
  })

  const status: GatewayStatus | undefined = data?.result

  const importMutation = useMutation({
    mutationFn: async (u: string) => {
      const r = await jsonFetch<any>("/api/v1/persona-proxy/subscription", {
        method: "PUT",
        body: JSON.stringify({ url: u }),
      })
      return r.result
    },
    onSuccess: (r) => {
      toast({
        title: "订阅已导入",
        description: `解析 ${r?.total_nodes ?? 0} 个节点，重载 ${r?.reload?.ok ? "成功" : "失败"}`,
      })
      queryClient.invalidateQueries({ queryKey: ["persona-proxy-status"] })
    },
    onError: (e: any) => {
      toast({ title: "导入失败", description: e?.message || String(e), variant: "destructive" })
    },
  })

  const reloadMutation = useMutation({
    mutationFn: () => jsonFetch<any>("/api/v1/persona-proxy/reload", { method: "POST" }),
    onSuccess: (r) => {
      toast({ title: "已重载", description: r?.result?.reload?.ok ? "配置已热重载" : "重载失败，请检查网关进程" })
      queryClient.invalidateQueries({ queryKey: ["persona-proxy-status"] })
    },
    onError: (e: any) => toast({ title: "重载失败", description: e?.message || String(e), variant: "destructive" }),
  })

  const handleImport = () => {
    const u = url.trim()
    if (!u.startsWith("http://") && !u.startsWith("https://")) {
      toast({ title: "URL 无效", description: "请输入 http/https 开头的订阅链接", variant: "destructive" })
      return
    }
    importMutation.mutate(u)
  }

  const listeningCount = status ? Object.values(status.ports).filter(Boolean).length : 0

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Persona"
        title="代理网关"
        description="填写 Clash 订阅链接，自动解析节点并生成 6 个地区的专属代理端口（7771-7776）。"
        actions={
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        }
      />

      <PageSection title="订阅" description="导入订阅 URL 后，网关会按地区自动挑选节点并热重载，无需重启。">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[320px] space-y-1">
            <label className="text-sm text-foreground/70">订阅 URL</label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://... (Clash / base64 订阅链接)"
            />
          </div>
          <Button onClick={handleImport} disabled={importMutation.isPending}>
            {importMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
            导入并生效
          </Button>
          <Button variant="outline" onClick={() => reloadMutation.mutate()} disabled={reloadMutation.isPending}>
            {reloadMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Server className="mr-2 h-4 w-4" />}
            重载现有配置
          </Button>
        </div>
        {status?.subscription_url && (
          <p className="mt-3 text-xs text-foreground/50 break-all">
            当前订阅：{status.subscription_url}
            {status.updated_at ? `　·　更新于 ${status.updated_at}` : ""}
          </p>
        )}
      </PageSection>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>监听端口</CardDescription>
            <CardTitle className="text-2xl">{listeningCount}<span className="text-sm text-foreground/50">/6</span></CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>网关控制</CardDescription>
            <CardTitle className="text-xl flex items-center gap-2">
              {status?.controller_ok === undefined && isLoading ? (
                <span className="text-foreground/50">—</span>
              ) : status?.controller_ok ? (
                <><CheckCircle2 className="h-5 w-5 text-emerald-500" /> 在线</>
              ) : (
                <><XCircle className="h-5 w-5 text-red-500" /> 离线</>
              )}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="col-span-2">
          <CardHeader className="pb-2">
            <CardDescription>用途</CardDescription>
            <CardTitle className="text-base font-normal">Persona 指纹按账号的 persona_proxy 地区注入对应端口，自动对齐 locale / 时区</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <PageSection title="地区映射" description="每个地区一个 mixed 代理端口，路由到该国的订阅节点。">
        {error ? (
          <div className="text-sm text-red-500">加载失败：{String((error as any)?.message || error)}</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>地区</TableHead>
                <TableHead>端口</TableHead>
                <TableHead>绑定节点</TableHead>
                <TableHead>状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {REGION_ORDER.map((r) => {
                const port = status?.regions?.[r.key]?.port
                const node = status?.mapping?.[r.key]
                const up = status?.ports?.[r.key]
                return (
                  <TableRow key={r.key}>
                    <TableCell className="font-medium">
                      {r.flag} {r.name}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono">{port ?? "—"}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[320px] truncate" title={node}>
                      {node || <span className="text-foreground/40">未匹配</span>}
                    </TableCell>
                    <TableCell>
                      {up === undefined ? (
                        <span className="text-foreground/40">—</span>
                      ) : up ? (
                        <Badge className="bg-emerald-500/15 text-emerald-600"><CheckCircle2 className="mr-1 h-3 w-3" /> 监听中</Badge>
                      ) : (
                        <Badge className="bg-red-500/15 text-red-600"><XCircle className="mr-1 h-3 w-3" /> 未监听</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </PageSection>
    </div>
  )
}