import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface PaginationProps {
  page: number
  pageCount: number
  onPageChange: (page: number) => void
  total?: number
  className?: string
}

/** Build a compact pagination window, e.g. [1, "…", 4, 5, 6, "…", 20] */
function paginationWindow(page: number, pageCount: number, spread = 1): (number | "…")[] {
  if (pageCount <= 0) return []
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1)

  const pages: (number | "…")[] = [1]
  const start = Math.max(2, page - spread)
  const end = Math.min(pageCount - 1, page + spread)

  if (start > 2) pages.push("…")
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < pageCount - 1) pages.push("…")
  pages.push(pageCount)
  return pages
}

/**
 * Compact, monochrome console-style pagination.
 * Signals that pagination is unnecessary when there is only one page.
 */
export function Pagination({ page, pageCount, onPageChange, total, className }: PaginationProps) {
  const pages = React.useMemo(() => paginationWindow(page, pageCount), [page, pageCount])
  if (pageCount <= 1) return null

  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-2", className)}>
      <div className="text-[11px] text-muted-foreground">
        {total != null && <span>共 {total} 条 · </span>}第 {page} / {pageCount} 页
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 border border-border bg-card text-xs text-foreground/70 hover:text-foreground"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          上一页
        </Button>
        {pages.map((p, i) =>
          p === "…" ? (
            <span key={`gap-${i}`} className="px-1 text-xs text-muted-foreground">…</span>
          ) : (
            <Button
              key={p}
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 min-w-7 px-1.5 text-xs",
                p === page
                  ? "bg-foreground text-background"
                  : "border border-border bg-card text-foreground/70 hover:text-foreground"
              )}
              onClick={() => onPageChange(p)}
            >
              {p}
            </Button>
          )
        )}
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 border border-border bg-card text-xs text-foreground/70 hover:text-foreground"
          onClick={() => onPageChange(Math.min(pageCount, page + 1))}
          disabled={page >= pageCount}
        >
          下一页
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
