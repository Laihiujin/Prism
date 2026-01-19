"use client"

import { Menu, Search } from "lucide-react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { motion } from "framer-motion"
import { useState, useMemo, useEffect } from "react"
import { useToast } from "@/components/ui/use-toast"
import { useQueryClient } from "@tanstack/react-query"
import debounce from "lodash.debounce"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

interface NavbarProps extends React.HTMLAttributes<HTMLDivElement> {
    isConnected?: boolean
    environment?: string
    onMenuClick?: () => void
}

export function NavbarNew({ className, onMenuClick }: NavbarProps) {
    const { toast } = useToast()
    const queryClient = useQueryClient()




    const router = useRouter()
    const searchParams = useSearchParams()
    const pathname = usePathname()

    const handleSearch = useMemo(
        () =>
            debounce((term: string) => {
                const params = new URLSearchParams(searchParams.toString())
                if (term) {
                    params.set("q", term)
                } else {
                    params.delete("q")
                }
                router.replace(`${pathname}?${params.toString()}`)
            }, 300),
        [searchParams, pathname, router]
    )

    return (
        <motion.header
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className={cn(
                "sticky top-0 z-50 flex h-16 items-center justify-between border-b border-white/10 bg-black/40 px-6 backdrop-blur-xl relative",
                className
            )}
        >
            {/* Left: Branding/Nav (Empty for now or could differ) */}
            <div className="flex items-center gap-4">
                {onMenuClick && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="md:hidden text-white/70 hover:text-white hover:bg-white/10"
                        onClick={onMenuClick}
                        aria-label="打开菜单"
                    >
                        <Menu className="h-5 w-5" />
                    </Button>
                )}
            </div>

            {/* Center: Search */}
            <div className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 group md:block">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-hover:text-white" />
                <Input
                    placeholder="Search..."
                    className="h-9 w-64 border-white/10 bg-black pl-9 text-sm text-white transition-all focus:w-80 focus:border-white/20 focus:bg-black focus:shadow-glow-white/10 rounded-2xl"
                    defaultValue={searchParams.get("q")?.toString()}
                    onChange={(e) => handleSearch(e.target.value)}
                />
            </div>

            {/* Right: System Status & User (Removed) */}
            <div className="flex items-center gap-4">
            </div>
        </motion.header>
    )
}
