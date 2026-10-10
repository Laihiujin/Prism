"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { backendBaseUrl } from "@/lib/env"

export function MaterialPresetMenu({ materialId, onEdit }: { materialId: string; onEdit: (presetId: string) => void }) {
    const [presets, setPresets] = useState<Record<string, { name: string }>>({})
    const [name, setName] = useState("")
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)
    const [open, setOpen] = useState(false)
    const load = async () => {
        try {
            const response = await fetch(`${backendBaseUrl}/api/v1/files/${materialId}/presets`)
            const payload = await response.json()
            if (!response.ok) throw new Error(payload.detail || "预设读取失败")
            setPresets(payload.data || {}); setError("")
        } catch (error) { setError(error instanceof Error ? error.message : "预设读取失败") }
    }
    const edit = (id: string) => { setOpen(false); onEdit(id) }
    return <Popover open={open} onOpenChange={next => { setOpen(next); if (next) void load() }}>
        <PopoverTrigger asChild><Button size="sm" variant="secondary">平台预设</Button></PopoverTrigger>
        <PopoverContent align="end" className="w-72 space-y-3 rounded-xl">
            <div className="text-sm font-medium">选择预设后编辑</div>
            <button className="block w-full rounded-lg p-2 text-left text-sm hover:bg-accent" onClick={() => edit("default")}>通用配置</button>
            {Object.entries(presets).map(([id, preset]) => <button key={id} className="block w-full rounded-lg p-2 text-left text-sm hover:bg-accent" onClick={() => edit(id)}>{preset.name}</button>)}
            <Input aria-label="新预设名称" placeholder="新预设名称" value={name} onChange={event => setName(event.target.value)} />
            <Button className="w-full bg-white text-black hover:bg-zinc-200" disabled={busy || !name.trim()} onClick={async () => {
                setBusy(true)
                try {
                    const id = crypto.randomUUID()
                    const response = await fetch(`${backendBaseUrl}/api/v1/files/${materialId}/presets/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim(), platform: "all", data: {} }) })
                    const payload = await response.json()
                    if (!response.ok) throw new Error(payload.detail || "创建预设失败")
                    setName(""); edit(id)
                } catch (error) { setError(error instanceof Error ? error.message : "创建预设失败") }
                finally { setBusy(false) }
            }}>{busy ? "创建中…" : "新增并编辑"}</Button>
            {error ? <p role="alert" className="text-xs text-red-400">{error}</p> : null}
        </PopoverContent>
    </Popover>
}
