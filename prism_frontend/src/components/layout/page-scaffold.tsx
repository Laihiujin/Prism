import { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface PageHeaderProps {
  title: string
  description?: string
  eyebrow?: string
  actions?: ReactNode
  align?: "start" | "center"
}

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  align = "start",
}: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-6 px-1">
      <div className={cn("space-y-2", align === "center" && "text-center w-full")}>
        {eyebrow && (
          <p className="text-sm uppercase tracking-[0.3em] text-white/50">
            {eyebrow}
          </p>
        )}
        <h1 className="text-3xl font-semibold leading-tight text-white">{title}</h1>
        {description && (
          <p className="text-sm text-white/60">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  )
}

interface PageSectionProps {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  contentClassName?: string
}

export function PageSection({
  title,
  description,
  actions,
  children,
  footer,
  className,
  contentClassName,
}: PageSectionProps) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-3xl border border-white/10 bg-black shadow-[0_30px_80px_-60px_rgba(0,0,0,0.9)]",
        className
      )}
    >
      {(title || description || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/5 px-5 py-4">
          <div className="space-y-1">
            {title && <h2 className="text-lg font-semibold text-white">{title}</h2>}
            {description && <p className="text-sm text-white/60">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("space-y-4 px-5 py-4", contentClassName)}>
        {children}
      </div>
      {footer && (
        <div className="border-t border-white/5 px-5 py-4">
          {footer}
        </div>
      )}
    </section>
  )
}
