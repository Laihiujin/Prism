import Link from "next/link"

export function PublishBreadcrumb({ platform, mode }: { platform: string; mode: "video" | "note" }) {
  return <nav aria-label="面包屑" className="flex items-center gap-2 text-xs text-muted-foreground">
    <Link href="/publish/matrix" className="hover:text-foreground">矩阵发布</Link><span aria-hidden="true">/</span>
    <Link href={mode === "video" ? "/publish/matrix" : "/publish/note"} className="hover:text-foreground">{mode === "video" ? "视频发布" : "图片发布"}</Link><span aria-hidden="true">/</span>
    <span aria-current="page" className="text-foreground">{platform}</span>
  </nav>
}
