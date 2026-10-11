"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type PickerAccount = { id: string | number; name?: string | null; username?: string | null; user_id?: string | number | null; nickname?: string | null; note?: string | null; avatar?: string | null }
export function PlatformAccountPicker({ accounts, selected, onChange }: { accounts: PickerAccount[]; selected: string[]; onChange: (ids: string[]) => void }) {
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const name = (account: PickerAccount) => account.name || account.nickname || account.username || String(account.user_id || account.id)
  const matches = accounts.filter(account => [name(account), account.id, account.user_id, account.note].join(" ").toLowerCase().includes(search.trim().toLowerCase()))
  const pages = Math.max(1, Math.ceil(matches.length / 10))
  const currentPage = Math.min(page, pages)
  const ids = matches.map(account => String(account.id))
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id])
  return <div className="space-y-3" aria-label="平台账号列表">
    <Input placeholder="搜索账号、ID、备注" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} />
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" disabled={!ids.length} onClick={() => onChange(Array.from(new Set([...selected, ...ids])))}>全选</Button>
      <Button size="sm" variant="outline" disabled={!ids.length} onClick={() => onChange([...selected.filter(id => !ids.includes(id)), ...ids.filter(id => !selected.includes(id))])}>反选</Button>
      <span className="text-xs text-muted-foreground">匹配 {matches.length} 个 · 已选 {selected.length} 个</span>
    </div>
    <p className="text-xs text-muted-foreground">全选 / 反选作用于所有搜索结果，包含其他分页。</p>
    <div className="grid gap-2">
      {matches.slice((currentPage - 1) * 10, currentPage * 10).map(account => <button type="button" key={account.id} role="checkbox" aria-checked={selected.includes(String(account.id))} onClick={() => toggle(String(account.id))} className={cn("flex items-center gap-3 border border-border/70 p-3 text-left", selected.includes(String(account.id)) && "border-primary bg-accent")}>
        <span className="text-base">{selected.includes(String(account.id)) ? "☑" : "☐"}</span>
        {account.avatar && <img src={account.avatar} alt="" className="h-8 w-8 rounded-full object-cover" referrerPolicy="no-referrer" />}
        <span className="min-w-0"><span className="block truncate text-sm">{name(account)}</span><span className="block truncate text-xs text-muted-foreground">ID: {account.user_id || account.id}{account.note ? ` · ${account.note}` : ""}</span></span>
      </button>)}
    </div>
    {!matches.length && <p className="py-5 text-center text-sm text-muted-foreground">暂无匹配账号</p>}
    <div className="flex items-center justify-between gap-2 text-xs">
      <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>上一页</Button>
      <span>第 {currentPage} / {pages} 页 · 每页 10 个</span>
      <Button size="sm" variant="outline" disabled={currentPage >= pages} onClick={() => setPage(currentPage + 1)}>下一页</Button>
    </div>
  </div>
}
