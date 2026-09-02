'use client'

import React, { useEffect, useState, Suspense } from "react"
import { usePathname } from "next/navigation"
import { HermesEmbeddedHost } from "@/components/hermes/hermes-embedded-host"
import { PersonaEmbeddedHost } from "@/components/persona/persona-embedded-host"
import { SidebarNew } from "@/components/layout/sidebar-new"
import { NavbarNew } from "@/components/layout/navbar-new"
import { Sheet, SheetContent } from "@/components/ui/sheet"

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const pathname = usePathname()
  const hermesActive = pathname === "/ai-agent"
  const personaActive = pathname === "/persona"
  const hermesChatActive = pathname === "/hermes-chat"
  const embeddedActive = hermesActive || hermesChatActive || personaActive

  // Keep the primary navigation readable after route changes; users can still
  // collapse it manually with the control at the bottom of the sidebar.
  useEffect(() => {
    setCollapsed(false)
  }, [pathname])

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-background text-foreground selection:bg-black selection:text-foreground md:min-h-screen md:w-full">
      {/* Pure black minimal background */}
      <div className="fixed inset-0 z-0 pointer-events-none bg-black" />

      {/* Desktop sidebar */}
      <div className="hidden sm:flex relative z-20">
          <SidebarNew collapsed={false} setCollapsed={setCollapsed} className="z-20" />
      </div>

      {/* Mobile sidebar (sheet) */}
      <div className="sm:hidden">
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
        <main className="relative flex-1 overflow-y-auto bg-background p-0">
          <Suspense fallback={null}>
            <div className={embeddedActive ? "hidden" : "mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700"}>
              {children}
            </div>
          </Suspense>
          {hermesActive && <HermesEmbeddedHost active />}
          {hermesChatActive && (
            <div className="absolute inset-0 z-10 bg-black">
              <iframe
                src="http://127.0.0.1:8788/"
                title="HermesChat"
                className="block h-full w-full border-0 bg-black"
              />
            </div>
          )}
          {personaActive && <PersonaEmbeddedHost active />}
        </main>
      </div>
    </div>
  )
}
