"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  MessageSquare,
  Plus,
  Trash2,
  MoreVertical,
  Edit2,
  Check,
  X
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"

export interface Thread {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  metadata?: Record<string, any>
}

interface ThreadSidebarProps {
  threads: Thread[]
  currentThreadId: string | null
  onSelectThread: (threadId: string) => void
  onCreateThread: () => void
  onDeleteThread: (threadId: string) => void
  onRenameThread: (threadId: string, newTitle: string) => void
  isLoading?: boolean
}

export function ThreadSidebar({
  threads,
  currentThreadId,
  onSelectThread,
  onCreateThread,
  onDeleteThread,
  onRenameThread,
  isLoading = false
}: ThreadSidebarProps) {
  const [editingId, setEditingId] = React.useState<string | null>(null)
  const [editValue, setEditValue] = React.useState("")

  const handleStartEdit = (thread: Thread) => {
    setEditingId(thread.id)
    setEditValue(thread.title)
  }

  const handleSaveEdit = (threadId: string) => {
    if (editValue.trim()) {
      onRenameThread(threadId, editValue.trim())
    }
    setEditingId(null)
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditValue("")
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "刚刚"
    if (diffMins < 60) return `${diffMins} 分钟前`
    if (diffHours < 24) return `${diffHours} 小时前`
    if (diffDays < 7) return `${diffDays} 天前`

    return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
  }

  return (
    <div className="flex h-full w-64 flex-col border-r border-white/10 bg-neutral-900/30 backdrop-blur-sm">
      {/* Header */}
      <div className="border-b border-white/10 p-4">
        <Button
          onClick={onCreateThread}
          className="w-full bg-white/10 hover:bg-white/20 text-white"
          size="sm"
        >
          <Plus className="mr-2 h-4 w-4" />
          新建对话
        </Button>
      </div>

      {/* Thread List */}
      <ScrollArea className="flex-1 p-2">
        <div className="space-y-1">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "group relative rounded-lg p-3 transition-all cursor-pointer",
                currentThreadId === thread.id
                  ? "bg-white/15 text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              )}
              onClick={() => {
                if (editingId !== thread.id) {
                  onSelectThread(thread.id)
                }
              }}
            >
              <div className="flex items-start gap-2">
                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-white/60" />

                <div className="flex-1 min-w-0">
                  {editingId === thread.id ? (
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            handleSaveEdit(thread.id)
                          } else if (e.key === "Escape") {
                            handleCancelEdit()
                          }
                        }}
                        className="h-7 bg-black/30 border-white/20 text-white text-sm"
                        autoFocus
                      />
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={() => handleSaveEdit(thread.id)}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={handleCancelEdit}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="truncate text-sm font-medium">
                        {thread.title}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-white/40">
                        <span>{formatDate(thread.updated_at)}</span>
                        {thread.message_count > 0 && (
                          <>
                            <span>·</span>
                            <span>{thread.message_count} 条消息</span>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>

                {editingId !== thread.id && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical className="h-3 w-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleStartEdit(thread)}>
                        <Edit2 className="mr-2 h-4 w-4" />
                        重命名
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => onDeleteThread(thread.id)}
                        className="text-red-500 focus:text-red-500"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-white/10 p-3">
        <div className="text-xs text-white/40 text-center">
          共 {threads.length} 个对话
        </div>
      </div>
    </div>
  )
}
