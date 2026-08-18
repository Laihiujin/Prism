import React, { useState, useCallback } from "react"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import {
  Users,
  Image,
  Send,
  Plus,
  Trash2,
  Database,
  Zap,
  Settings,
  FileText,
} from "lucide-react"

interface QuickCommand {
  id: string
  label: string
  description: string
  icon: React.ReactNode
  command: string
  category: "accounts" | "materials" | "publish" | "admin"
}

interface AIQuickCommandPaletteProps {
  onCommandSelect?: (command: string) => void
  isLoading?: boolean
}

export function AIQuickCommandPalette({
  onCommandSelect,
  isLoading = false,
}: AIQuickCommandPaletteProps) {
  const [open, setOpen] = useState(false)

  const commands: QuickCommand[] = [
    // 账号管理
    {
      id: "list-accounts",
      label: "列出所有账号",
      description: "查看已配置的社媒账号列表",
      icon: <Users className="h-4 w-4" />,
      command: "[EXEC]list_accounts()[/EXEC]",
      category: "accounts",
    },
    {
      id: "add-account",
      label: "添加新账号",
      description: "新增一个社交媒体账号",
      icon: <Plus className="h-4 w-4" />,
      command: "[EXEC]add_account(platform='douyin',cookies=...)[/EXEC]",
      category: "accounts",
    },
    {
      id: "delete-account",
      label: "删除账号",
      description: "移除指定的社交媒体账号",
      icon: <Trash2 className="h-4 w-4" />,
      command: "[EXEC]delete_account(account_id='...')[/EXEC]",
      category: "accounts",
    },
    {
      id: "account-info",
      label: "账号信息",
      description: "查看账号详细信息（粉丝、等级等）",
      icon: <Database className="h-4 w-4" />,
      command: "[EXEC]get_account_info(account_id='...')[/EXEC]",
      category: "accounts",
    },

    // 素材管理
    {
      id: "list-materials",
      label: "列出素材库",
      description: "查看可用的视频/图片素材",
      icon: <Image className="h-4 w-4" />,
      command: "[EXEC]list_materials(type='video')[/EXEC]",
      category: "materials",
    },

    // 发布相关
    {
      id: "publish-material",
      label: "一键发布素材",
      description: "将素材发布到指定平台",
      icon: <Send className="h-4 w-4" />,
      command: "[EXEC]publish_material(material_id='...',platforms=['douyin','xiaohongshu'])[/EXEC]",
      category: "publish",
    },
    {
      id: "batch-publish",
      label: "批量发布",
      description: "批量将素材发布到多个平台和账号",
      icon: <Zap className="h-4 w-4" />,
      command: "[EXEC]batch_publish(material_ids=[...],accounts=[...])[/EXEC]",
      category: "publish",
    },
    {
      id: "schedule-publish",
      label: "定时发布",
      description: "在指定时间发布素材",
      icon: <FileText className="h-4 w-4" />,
      command: "[EXEC]schedule_publish(material_id='...',publish_time='2024-01-01 12:00:00')[/EXEC]",
      category: "publish",
    },

    // 管理
    {
      id: "refresh-cookies",
      label: "刷新 Cookies",
      description: "重新获取社媒平台的登录凭证",
      icon: <Zap className="h-4 w-4" />,
      command: "[EXEC]refresh_cookies(platforms=['douyin','xiaohongshu'])[/EXEC]",
      category: "admin",
    },
    {
      id: "system-status",
      label: "系统状态",
      description: "检查系统运行状态和资源使用",
      icon: <Settings className="h-4 w-4" />,
      command: "[EXEC]get_system_status()[/EXEC]",
      category: "admin",
    },
  ]

  const categories = {
    accounts: "账号管理",
    materials: "素材管理",
    publish: "发布管理",
    admin: "系统管理",
  }

  const groupedCommands = commands.reduce(
    (acc, cmd) => {
      const category = cmd.category
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category].push(cmd)
      return acc
    },
    {} as Record<string, QuickCommand[]>
  )

  const handleCommandSelect = (command: QuickCommand) => {
    onCommandSelect?.(command.command)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="w-full justify-start gap-2 bg-white/5 border-white/20 text-white/60 hover:bg-white/10 hover:text-white"
          disabled={isLoading}
        >
          <Zap className="h-4 w-4" />
          <span>快速命令...</span>
          <kbd className="ml-auto hidden h-5 select-none items-center gap-1 rounded border border-white/20 bg-white/5 px-1.5 font-mono text-xs text-white/40 sm:flex">
            <span>⌘</span>K
          </kbd>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0 bg-gradient-to-b from-slate-900 to-slate-800 border-white/10">
        <Command className="bg-transparent">
          <CommandInput
            placeholder="搜索命令..."
            className="border-white/10 text-white placeholder:text-white/40"
          />
          <CommandEmpty className="text-white/50 p-4">未找到匹配的命令</CommandEmpty>
          <CommandList className="max-h-96">
            {Object.entries(groupedCommands).map(([categoryKey, cmds]) => (
              <CommandGroup
                key={categoryKey}
                heading={
                  <span className="text-white/60">
                    {categories[categoryKey as keyof typeof categories]}
                  </span>
                }
                className="text-white/60 [&_[cmdk-group-heading]]:text-white/40"
              >
                {cmds.map((cmd) => (
                  <CommandItem
                    key={cmd.id}
                    value={cmd.id}
                    onSelect={() => handleCommandSelect(cmd)}
                    className="aria-selected:bg-blue-600/30 aria-selected:text-white text-white/70 cursor-pointer hover:bg-white/10"
                  >
                    <div className="flex items-center justify-between w-full gap-2">
                      <div className="flex items-center gap-2 flex-1">
                        <span className="text-blue-400">{cmd.icon}</span>
                        <div className="flex-1">
                          <div className="font-medium text-white">{cmd.label}</div>
                          <div className="text-xs text-white/40">{cmd.description}</div>
                        </div>
                      </div>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
