"use client"

import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, RefreshCw, Server, ShieldCheck, CheckCircle2, XCircle, Trash2 } from "lucide-react"
import { PageHeader, PageSection } from "@/components/layout/page-scaffold"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
  port_map: Record<string, number>
  ports: Record<string, boolean>
  updated_at: string
  controller_ok: boolean
}

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

  const nodeEntries = useMemo(() => {
    if (!status?.port_map) return []
    return Object.entries(status.port_map)
      .sort((a, b) => a[1] - b[1])
      .map(([name, port]) => ({ name, port, up: status.ports?.[name] ?? false }))
  }, [status])

  const listeningCount = nodeEntries.filter((n) => n.up).length
  const totalNodes = nodeEntries.length

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
        description: `解析 ${r?.total_nodes ?? 0} 个节点，${r?.reload?.ok ? "热重载成功" : "重载失败"}`,
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
      toast({ title: "已重载", description: r?.result?.reload?.ok ? "配置已热重载" : "重载失败" })
      queryClient.invalidateQueries({ queryKey: ["persona-proxy-status"] })
    },
    onError: (e: any) => toast({ title: "重载失败", description: e?.message || String(e), variant: "destructive" }),
  })

  const clearMutation = useMutation({
    mutationFn: () => jsonFetch<any>("/api/v1/persona-proxy/subscription", { method: "DELETE" }),
    onSuccess: (r) => {
      toast({ title: "已取消导入", description: r?.result?.reload?.ok ? "所有端口已释放" : "配置已清空" })
      setUrl("")
      queryClient.invalidateQueries({ queryKey: ["persona-proxy-status"] })
    },
    onError: (e: any) => toast({ title: "取消失败", description: e?.message || String(e), variant: "destructive" }),
  })

  const handleImport = () => {
    const u = url.trim()
    if (!u.startsWith("http://") && !u.startsWith("https://")) {
      toast({ title: "URL 无效", description: "请输入 http/https 开头的订阅链接", variant: "destructive" })
      return
    }
    importMutation.mutate(u)
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Persona"
        title="代理网关"
        description="填写订阅链接，自动解析全部节点，每个节点分配独立 mixed 代理端口（8001 起）。"
        actions={
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        }
      />

      <PageSection title="订阅" description="导入后自动为每个节点分配端口并热重载，无需重启。">
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
            重载配置
          </Button>
          {status?.subscription_url && (
            <Button variant="destructive" onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending}>
              {clearMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              取消导入
            </Button>
          )}
        </div>
        {status?.subscription_url && (
          <p className="mt-3 text-xs text-foreground/50 break-all">
            当前订阅：{status.subscription_url}
            {status.updated_at ? ` · 更新于 ${status.updated_at}` : ""}
          </p>
        )}
      </PageSection>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>解析节点</CardDescription>
            <CardTitle className="text-2xl">{totalNodes}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>监听中</CardDescription>
            <CardTitle className="text-2xl">{listeningCount}<span className="text-sm text-foreground/50">/{totalNodes}</span></CardTitle>
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
      </div>

      <PageSection title="节点端口" description="每个节点分配独立的 HTTP+SOCKS mixed 代理端口，Persona 可直接使用。">
        {error ? (
          <div className="text-sm text-red-500">加载失败：{String((error as any)?.message || error)}</div>
        ) : nodeEntries.length === 0 ? (
          <div className="text-sm text-foreground/50">暂无节点，请先导入订阅</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">端口</TableHead>
                <TableHead>节点名称</TableHead>
                <TableHead className="w-[90px]">状态</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodeEntries.map((n) => (
                <TableRow key={n.name}>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">{n.port}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[400px] truncate" title={n.name}>
                    {n.name}
                  </TableCell>
                  <TableCell>
                    {n.up ? (
                      <Badge className="bg-emerald-500/15 text-emerald-600"><CheckCircle2 className="mr-1 h-3 w-3" /> 监听</Badge>
                    ) : (
                      <Badge className="bg-red-500/15 text-red-600"><XCircle className="mr-1 h-3 w-3" /> 未监听</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </PageSection>
    </div>
  )
}
