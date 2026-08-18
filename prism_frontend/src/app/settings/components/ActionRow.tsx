"use client"

import { Button } from "@/components/ui/button"
import { Loader2, LucideIcon } from "lucide-react"

interface ActionRowProps {
  icon: LucideIcon
  label: string
  description: string
  onAction: () => void
  loading?: boolean
}

export function ActionRow({
  icon: Icon,
  label,
  description,
  onAction,
  loading = false
}: ActionRowProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10 transition-colors">
      <div className="flex items-start gap-3 flex-1">
        <div className="p-2 bg-white/5 rounded-lg mt-0.5">
          <Icon className="w-4 h-4 text-white/70" />
        </div>
        <div className="flex-1">
          <div className="font-medium text-white">{label}</div>
          <div className="text-sm text-white/60 mt-0.5">{description}</div>
        </div>
      </div>
      <Button
        onClick={onAction}
        disabled={loading}
        variant="destructive"
        size="sm"
        className="ml-4 min-w-[80px]"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            {"\u6e05\u7406\u4e2d..."}
          </>
        ) : (
          "\u6e05\u7406"
        )}
      </Button>
    </div>
  )
}
