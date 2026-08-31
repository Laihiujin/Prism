'use client'

import React, { useState, Suspense } from "react"
import { usePathname } from "next/navigation"
import { HermesEmbeddedHost } from "@/components/hermes/hermes-embedded-host"
import { SidebarNew } from "@/components/layout/sidebar-new"
import { NavbarNew } from "@/components/layout/navbar-new"
import { Sheet, SheetContent } from "@/components/ui/sheet"

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const pathname = usePathname()
  const hermesActive = pathname === "/ai-agent"

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-background text-foreground selection:bg-black selection:text-foreground md:min-h-screen md:w-full">
      {/* Pure black minimal background */}
      <div className="fixed inset-0 z-0 pointer-events-none bg-black" />

      {/* Desktop sidebar */}
      <div className="hidden md:flex relative z-20">
        <SidebarNew collapsed={collapsed} setCollapsed={setCollapsed} className="z-20" />
      </div>

      {/* Mobile sidebar (sheet) */}
      <div className="md:hidden">
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent side="left" className="p-0 border-border">
            <SidebarNew
              collapsed={false}
              setCollapsed={() => { }}
              showCollapseToggle={false}
              onNavigate={() => setMobileNavOpen(false)}
              className="border-r border-border/80"
            />
          </SheetContent>
        </Sheet>
      </div>

      <div className="relative z-10 flex flex-1 flex-col overflow-hidden min-w-0">
        <Suspense fallback={<div className="h-16 border-b border-border bg-background/40" />}>
          <NavbarNew onMenuClick={() => setMobileNavOpen(true)} />
        </Suspense>
        <main className="relative flex-1 overflow-y-auto p-0">
          <Suspense fallback={null}>
            <div className={hermesActive ? "hidden" : "mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700"}>
              {children}
            </div>
          </Suspense>
          <HermesEmbeddedHost active={hermesActive} />
        </main>
      </div>
    </div>
  )
}
