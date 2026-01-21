
'use client'

import { useEffect } from "react"

function MSWComponent() {
  useEffect(() => {
    let mounted = true
    // Temporarily disabled MSW to allow real backend API calls
    // Uncomment below to enable MSW again
    /*
    if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
      import("@/mocks/browser").then((module) => {
        if (!mounted) return
        module.worker.start()
      })
    }
    */
    return () => {
      mounted = false
    }
  }, [])


  return null
}

export default MSWComponent
