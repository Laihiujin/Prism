"use client"

export default function PersonaStudioPage() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full flex-col">
      <div className="flex items-center justify-between border-b border-border/70 px-4 py-2">
        <div>
          <div className="font-medium text-foreground">Persona Studio</div>
          <div className="text-xs text-muted-foreground">
            内嵌浏览器身份 / 指纹 / Profile 管理后台（persona serve :8787 · dashboard :5173）
          </div>
        </div>
        <a
          href="http://127.0.0.1:5173"
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-border/70 bg-black px-3 py-1.5 text-xs text-foreground hover:bg-accent/40"
        >
          新窗口打开 ↗
        </a>
      </div>
      <iframe
        src="http://127.0.0.1:5173"
        className="h-full w-full flex-1 border-0"
        title="Persona Studio"
      />
    </div>
  )
}
