import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Simple horizontal/vertical separator.
 * Matches the shadcn/ui separator API to avoid import errors.
 */
const Separator = React.forwardRef<
  React.ElementRef<"div">,
  React.ComponentPropsWithoutRef<"div"> & { orientation?: "horizontal" | "vertical" }
>(({ className, orientation = "horizontal", role = "separator", ...props }, ref) => {
  return (
    <div
      ref={ref}
      role={role}
      aria-orientation={orientation}
      className={cn(
        "shrink-0 bg-border",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className
      )}
      {...props}
    />
  )
})
Separator.displayName = "Separator"

export { Separator }
