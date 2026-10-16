import { redirect } from "next/navigation"

export const dynamic = "force-dynamic"

export default function CmsPage() {
    const base = process.env.PRISM_CMS_URL || `http://127.0.0.1:${process.env.PRISM_CMS_PORT || "8441"}`
    redirect(new URL("/cms", base).toString())
}
