"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type HermesLogoIconProps = React.HTMLAttributes<HTMLSpanElement>

export function HermesLogoIcon({ className, style, ...props }: HermesLogoIconProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block shrink-0 bg-current", className)}
      style={{
        maskImage: "url(/hermes-agent-logo.svg)",
        maskRepeat: "no-repeat",
        maskPosition: "center",
        maskSize: "contain",
        WebkitMaskImage: "url(/hermes-agent-logo.svg)",
        WebkitMaskRepeat: "no-repeat",
        WebkitMaskPosition: "center",
        WebkitMaskSize: "contain",
        ...style,
      }}
      {...props}
    />
  )
}
