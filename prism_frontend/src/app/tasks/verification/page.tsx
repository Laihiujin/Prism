import Link from "next/link"
import { TaskVerifications } from "@/components/publish/task-verifications"

export default function PublishVerificationPage() {
  return <div className="mx-auto w-full max-w-[1440px] space-y-5 px-4 py-4 md:px-6 md:py-5">
    <nav aria-label="面包屑" className="text-sm text-muted-foreground"><Link href="/tasks" className="hover:underline">任务管理</Link> / 任务发布人工验证</nav>
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">任务发布人工验证</h1>
      <p className="text-sm text-muted-foreground">手动及批量发布的待验证账号集中展示，各账号独立回传、重新获取验证码。关闭弹窗不会取消任务；平台验证通过后继续发布。</p>
    </div>
    <TaskVerifications showEmpty />
  </div>
}
