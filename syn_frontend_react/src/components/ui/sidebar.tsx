import * as React from "react"
import { cn } from "@/lib/utils"

type SidebarContextValue = {
  collapsed: boolean
  toggle: () => void
}

const SidebarContext = React.createContext<SidebarContextValue | null>(null)

export function useSidebar() {
  const ctx = React.useContext(SidebarContext)
  if (!ctx) throw new Error("useSidebar must be used within SidebarProvider")
  return ctx
}

interface SidebarProviderProps {
  initialCollapsed?: boolean
  children: React.ReactNode
}

export function SidebarProvider({ initialCollapsed = false, children }: SidebarProviderProps) {
  const [collapsed, setCollapsed] = React.useState(initialCollapsed)
  const toggle = React.useCallback(() => setCollapsed((prev) => !prev), [])

  return (
    <SidebarContext.Provider value={{ collapsed, toggle }}>
      <div className="flex min-h-screen">{children}</div>
    </SidebarContext.Provider>
  )
}

export function SidebarInset({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex-1", className)}>{children}</div>
}

export function Sidebar({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement> & React.RefAttributes<HTMLElement>) {
  const { collapsed } = useSidebar()
  return (
    <aside
      className={cn(
        "hidden border-r border-white/10 bg-white/[0.02] backdrop-blur md:block",
        collapsed ? "w-16" : "w-64",
        className
      )}
      {...props}
    >
      {children}
    </aside>
  )
}

export function SidebarHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3", className)} {...props} />
}

export function SidebarContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-2", className)} {...props} />
}

export function SidebarFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-auto px-4 py-3", className)} {...props} />
}

export function SidebarTrigger({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & React.RefAttributes<HTMLButtonElement>) {
  const { toggle } = useSidebar()
  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-white/5 text-sm text-white transition hover:bg-white/10",
        className
      )}
      aria-label="切换侧边栏"
      {...props}
    >
      ≡
    </button>
  )
}
