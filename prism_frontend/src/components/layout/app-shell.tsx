'use client'

import React, { useState, Suspense } from "react"
import { usePathname } from "next/navigation"
import { HermesEmbeddedHost } from "@/components/hermes/hermes-embedded-host"
import { SidebarNew } from "@/components/layout/sidebar-new"
import { NavbarNew } from "@/components/layout/navbar-new"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import Aurora from "@/components/Aurora"

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const pathname = usePathname()
  const hermesActive = pathname === "/ai-agent"

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-background text-foreground selection:bg-primary/30 selection:text-foreground md:min-h-screen md:w-full">
      {/* SaaS ambient background: deep Aurora glow + soft radial fade */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 opacity-[0.55]">
          <Aurora
            colorStops={["#1E3A8A", "#0EA5E9", "#312E81", "#111827"]}
            amplitude={0.9}
            blend={0.35}
            speed={0.5}
          />
        </div>
        <div className="absolute inset-0 bg-ambient-fade" />
        {/* Depth vignette so content stays readable */}
        <div className="absolute inset-0 bg-[radial-gradient(120%_120%_at_50%_50%,transparent_55%,hsl(var(--background)/0.85)_100%)]" />
      </div>

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
