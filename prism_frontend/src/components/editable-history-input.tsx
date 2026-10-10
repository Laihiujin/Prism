"use client"
import { useState } from "react"
import { ChevronDown, Trash2, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export function EditableHistoryInput({ value, onChange, history, label, placeholder, onDelete }: { value: string; onChange: (value: string) => void; history: string[]; label: string; placeholder?: string; onDelete: (value: string) => Promise<void> }) {
    const [open, setOpen] = useState(false)
    const [deleting, setDeleting] = useState<string | null>(null)
    const remove = async (item: string) => {
        setDeleting(item)
        try {
            await onDelete(item)
            if (value === item) onChange("")
        } catch {
            // The parent displays the persistence error; keep the candidate intact.
        } finally {
            setDeleting(null)
        }
    }
    return <div className="relative">
        <Input aria-label={label} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} className="bg-black pr-10" />
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild><button type="button" aria-label={`选择历史${label}`} className="absolute right-0 top-0 flex h-9 w-9 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-blue-400"><ChevronDown className="h-4 w-4" /></button></PopoverTrigger>
            <PopoverContent align="end" className="w-[min(560px,85vw)] rounded-xl border border-zinc-700 bg-zinc-950 p-2 text-zinc-100">
                <div className="max-h-64 overflow-y-auto">
                    {history.length ? history.map(item => <div key={item} className="flex items-center gap-1 rounded-lg hover:bg-zinc-900">
                        <button type="button" disabled={deleting !== null} aria-pressed={item === value} className="min-w-0 flex-1 rounded-lg px-3 py-2 text-left text-sm break-words focus-visible:bg-zinc-900" onClick={() => { onChange(item); setOpen(false) }}>{item}</button>
                        <button type="button" disabled={deleting !== null} aria-label={`删除${label}：${item}`} title={`删除这条${label}`} className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-zinc-400 hover:bg-zinc-800 hover:text-red-400 disabled:opacity-50" onClick={() => void remove(item)}>{deleting === item ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}</button>
                    </div>) : <p className="px-3 py-2 text-xs text-muted-foreground">尚无生成记录，可以直接输入。</p>}
                </div>
            </PopoverContent>
        </Popover>
    </div>
}
