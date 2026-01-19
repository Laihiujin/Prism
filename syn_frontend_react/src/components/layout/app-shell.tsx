'use client'

import { useState, Suspense } from "react"
import { SidebarNew } from "@/components/layout/sidebar-new"
import { NavbarNew } from "@/components/layout/navbar-new"
import { Sheet, SheetContent } from "@/components/ui/sheet"

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-black text-foreground selection:bg-white/20 selection:text-white md:min-h-screen md:w-full">
      {/* Animated Background */}
      <div className="fixed inset-0 z-0">
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />
        {/* Radial Gradient (White/Silver) */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_800px_at_50%_-30%,#ffffff10,transparent)]" />
      </div>

      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <SidebarNew collapsed={collapsed} setCollapsed={setCollapsed} className="z-20" />
      </div>

      {/* Mobile sidebar (sheet) */}
      <div className="md:hidden">
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent side="left" className="p-0 bg-black border-white/10">
            <SidebarNew
              collapsed={false}
              setCollapsed={() => { }}
              showCollapseToggle={false}
              onNavigate={() => setMobileNavOpen(false)}
              className="border-r border-white/5"
            />
          </SheetContent>
        </Sheet>
      </div>

      <div className="relative z-10 flex flex-1 flex-col overflow-hidden min-w-0">
        <Suspense fallback={<div className="h-16 border-b border-white/10 bg-black/40" />}>
          <NavbarNew onMenuClick={() => setMobileNavOpen(true)} />
        </Suspense>
        <main className="flex-1 overflow-y-auto p-0">
          <Suspense fallback={null}>
            <div className="mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
              {children}
            </div>
          </Suspense>
        </main>
      </div>
    </div>
  )
}
