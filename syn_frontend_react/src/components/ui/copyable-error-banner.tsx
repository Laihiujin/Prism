"use client"

import { useState } from "react"
import { X, Copy, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface CopyableErrorBannerProps {
  message: string
  onDismiss?: () => void
  className?: string
}

export function CopyableErrorBanner({ message, onDismiss, className }: CopyableErrorBannerProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy:", err)
    }
  }

  return (
    <div
      className={cn(
        "relative flex items-center justify-between gap-3 bg-red-500/10 border border-red-500/50 px-4 py-3 text-red-600 dark:text-red-400",
        className
      )}
    >
      <div className="flex-1 flex items-center gap-2">
        <span className="text-sm font-medium">✗ 无法连接到 Supervisor:</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className={cn(
            "h-auto py-1 px-2 text-xs font-mono hover:bg-red-500/20",
            copied && "text-green-600 dark:text-green-400"
          )}
        >
          {message}
          {copied ? <Check className="ml-1.5 h-3 w-3" /> : <Copy className="ml-1.5 h-3 w-3" />}
        </Button>
      </div>

      {onDismiss && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onDismiss}
          className="h-6 w-6 hover:bg-red-500/20"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">关闭</span>
        </Button>
      )}
    </div>
  )
}
