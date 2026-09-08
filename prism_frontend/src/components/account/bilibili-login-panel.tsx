"use client"

/**
 * B站多方式登录面板（账号页弹窗内嵌）。
 *
 * 方式矩阵（对应后端 /api/v1/auth/bilibili/*）：
 *  - 扫码：走账号页主流程（二维码登录），此处不重复提供。
 *  - 短信：发码 → (极验 challenge/validate 补发) → 凭 sms_token 登录。
 *    完整回传调度：POST /sms/send → {sms_token}（或 need_recaptcha +
 *    recaptcha_url，需先 POST /sms/recaptcha 补发）→ POST /sms/confirm。
 *  - 账密：用户名/手机号 + 密码登录。
 *    完整调度：POST /password/prepare → {pwd_token} → POST /password {pwd_token,
 *    password, challenge?, validate?, seccode?}，返回 success / need_captcha（内嵌
 *    geetest 滑块） / need_sms（短信二次验证，POST /password/sms-confirm）。
 *
 * 成功回调 onLoginDone 后，父组件负责刷新账号列表并关闭弹窗。
 */

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { KeyRound, Loader2, MessageSquareText, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/use-toast"
import { backendBaseUrl } from "@/lib/env"

interface Props {
  accountId: string
  onLoginDone?: () => void
}

type Phase = "idle" | "busy" | "done"

function describeError(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) return value
  if (value && typeof value === "object") {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === "string" && detail.trim()) return detail
  }
  return fallback
}

/**
 * 内嵌 geetest 滑块（gt4）。
 * 仅当后端下发 need_captcha 并给出 gt / challenge 时渲染。
 * 通过官方 initGeetest（极验 v3）在容器内生成滑块，用户点过滑块后回调 onDone(validate)。
 */
declare global {
  interface Window {
    initGeetest?: (
      userConfig: {
        gt: string
        challenge: string
        product?: string
        lang?: string
        https?: boolean
        protocol?: string
        getType?: Record<string, unknown>
      },
      callback: (captchaObj: GeetestInst) => void
    ) => void
    geetest?: unknown
  }
}

interface GeetestInst {
  onSuccess: (cb: () => void) => void
  onError: (cb: (err: unknown) => void) => void
  onClose?: (cb: () => void) => void
  appendTo: (selector: string | HTMLElement) => void
  getValidate: () => { geetest_challenge: string; geetest_validate: string; geetest_seccode: string }
}

let geetestScriptLoaded = false
function loadGeetestScript(onDone: () => void, onError: (m: string) => void) {
  if (geetestScriptLoaded) {
    onDone()
    return
  }
  const existing = document.querySelector<HTMLScriptElement>('script[data-geetest-loader="1"]')
  if (existing) {
    existing.addEventListener("load", onDone, { once: true })
    existing.addEventListener("error", () => onError("geetest 脚本加载失败"), { once: true })
    return
  }
  const s = document.createElement("script")
  s.src = "https://static.geetest.com/static/tools/gt.js"
  s.async = true
  s.dataset.geetestLoader = "1"
  s.addEventListener("load", onDone, { once: true })
  s.addEventListener("error", () => onError("geetest 脚本加载失败"), { once: true })
  document.body.appendChild(s)
  geetestScriptLoaded = true
}

function GeetestEmbed({ gt, challenge, onDone, onError }: {
  gt: string
  challenge: string
  onDone: (validate: string, challenge: string) => void
  onError: (m: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<"loading" | "ready" | "idle" | "error">("loading")
  // 稳定的容器 id：geetest4 通过 captcha 字段把滑块渲染进该元素
  const containerId = useRef(`gt-embed-${Math.random().toString(36).slice(2, 10)}`).current

  useEffect(() => {
    if (!gt && !challenge) {
      setState("error")
      return
    }
    // 初始化超时：8 秒未回调则报错，避免永久"加载中"+大占位
    const timeout = setTimeout(() => {
      setState((prev) => {
        if (prev === "loading") {
          onError("滑块初始化超时，请重试")
          return "error"
        }
        return prev
      })
    }, 8000)

    loadGeetestScript(() => {
      if (typeof window === "undefined" || !window.initGeetest) {
        clearTimeout(timeout)
        setState("error")
        onError("geetest 初始化函数不可用")
        return
      }
      // v3 API：initGeetest(config, callback)，回调收到 captcha 实例
      window.initGeetest(
        {
          gt,
          challenge,
          product: "embed",
          lang: "zho",
        },
        (captcha) => {
          clearTimeout(timeout)
          captcha.onSuccess(() => {
            setState("ready")
            const v = (captcha.getValidate?.() ?? {}) as {
              geetest_challenge?: string
              geetest_validate?: string
              geetest_seccode?: string
            }
            if (!v.geetest_validate) {
              setState("error")
              onError("滑块返回为空，请重试")
              return
            }
            onDone(v.geetest_validate, v.geetest_challenge || challenge)
          })
          captcha.onError((err) => {
            setState("error")
            const m = (err as { msg?: string } | undefined)?.msg || String(err)
            onError(m || "geetest 验证出错")
          })
          captcha.onClose?.(() => setState("idle"))
          // 用 DOM 节点引用 appendTo（勿用 id 字符串；portal/动态 id 下 querySelector 可能失效）
          const target = document.getElementById(containerId) || containerRef.current
          if (target) {
            captcha.appendTo(target)
          } else {
            onError("滑块容器未就绪")
          }
        }
      )
    }, (m) => {
      clearTimeout(timeout)
      setState("error")
      onError(m)
    })
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gt, challenge])

  return (
    <div>
      {state === "loading" && (
        <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> 正在加载滑块验证…
        </p>
      )}
      {state === "error" && (
        <p className="text-[11px] text-red-400">滑块验证加载失败，请重试。</p>
      )}
      {/* 用 portal 把滑块挂到 body 顶层 + 最高 z-index，脱离登录弹窗(DialogOverlay z-50)遮挡，
          确保拖动不受弹窗层级拦截。成功后(state==="ready")不再渲染，避免残留浮层。 */}
      {typeof document !== "undefined" &&
        state !== "ready" &&
        createPortal(
          <div
            id={containerId}
            ref={containerRef}
            className="relative overflow-visible"
            style={{
              position: "fixed",
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
              zIndex: 9999,
              width: 340,
              minHeight: 248,
              background: "#fff",
              borderRadius: 12,
              boxShadow: "0 8px 40px rgba(0,0,0,0.35)",
              padding: 8,
            }}
          />,
          document.body
        )}
    </div>
  )
}

export function BilibiliLoginPanel({ accountId, onLoginDone }: Props) {
  const { toast } = useToast()
  const [phone, setPhone] = useState("")
  const [countryCode, setCountryCode] = useState("86")
  const [smsCode, setSmsCode] = useState("")
  // 短信发送会话：send/recaptcha 后由后端下发，confirm 时回传
  const [smsToken, setSmsToken] = useState<string | null>(null)
  // 极验（need_recaptcha）中间态——短信与账密共用内嵌 geetest
  const [recaptchaUrl, setRecaptchaUrl] = useState<string | null>(null)
  const [smsGeetest, setSmsGeetest] = useState<{
    gt: string
    challenge: string
    recaptcha_token: string
    showVerify: boolean
  } | null>(null)
  // 账密
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")
  const [altEnabled, setAltEnabled] = useState<boolean | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const loadedRef = useRef(false)

  const api = (path: string) => `${backendBaseUrl}/api/v1/auth/bilibili${path}`

  // 查询备选登录是否开放（默认开启；后端 ALLOW_BILIBILI_ALT_LOGIN=false 时关闭）
  const checkEnabled = async () => {
    if (loadedRef.current) return
    loadedRef.current = true
    try {
      const res = await fetch(api("/alt-enabled"))
      const data = await res.json().catch(() => null)
      setAltEnabled(Boolean(data?.enabled))
    } catch {
      setAltEnabled(null)
    }
  }

  const run = async (action: string, fn: () => Promise<Response>) => {
    setBusyAction(action)
    setPhase("busy")
    try {
      const res = await fn()
      const payload = await res.json().catch(() => ({}))
      if (!res.ok || payload?.success === false) {
        throw new Error(describeError(payload?.detail ?? payload?.message, `请求失败(${res.status})`))
      }
      return payload
    } finally {
      setBusyAction(null)
      setPhase("idle")
    }
  }

  const resetSmsSession = () => {
    setSmsToken(null)
    setRecaptchaUrl(null)
    setSmsGeetest(null)
  }

  const handleSendSms = async () => {
    if (!/^\d{6,13}$/.test(phone.trim())) {
      toast({ variant: "destructive", title: "手机号格式不正确" })
      return
    }
    try {
      const payload = await run("sms-send", () =>
        fetch(api("/sms/send"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone: phone.trim(), country_code: countryCode }),
        })
      )
      if (payload?.state === "sent" && payload?.sms_token) {
        resetSmsSession()
        setSmsToken(payload.sms_token)
        toast({ title: "验证码已发送", description: "请查收短信（B站）后输入。" })
        return
      }
      if (payload?.state === "need_recaptcha") {
        if (!payload?.sms_token) throw new Error("后端未返回短信会话 token")
        setSmsToken(payload.sms_token)
        setRecaptchaUrl(payload?.recaptcha_url ?? null)
        // 内嵌极验：直接用后端下发的 gt / challenge 渲染滑块
        setSmsGeetest({
          gt: payload?.geetest_gt ?? "",
          challenge: payload?.geetest_challenge ?? payload?.geetest_gt ?? "",
          recaptcha_token: "",
          showVerify: true,
        })
        toast({ title: "需要滑块验证", description: "请完成下方滑块验证。", })
        return
      }
      throw new Error(payload?.message || "验证码发送失败")
    } catch (err) {
      toast({ variant: "destructive", title: "发送失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  // 内嵌 geetest 滑块通过后，自动提交 /sms/recaptcha 补发验证码
  const handleSmsGeetestDone = async (validate: string, gchallenge: string) => {
    const challenge = gchallenge || smsGeetest?.challenge || ""
    try {
      const payload = await run("sms-recaptcha", () =>
        fetch(api("/sms/recaptcha"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sms_token: smsToken,
            challenge,
            validate,
          }),
        })
      )
      if (payload?.state === "sent" && payload?.sms_token) {
        setRecaptchaUrl(null)
        setSmsGeetest(null)
        setSmsToken(payload.sms_token)
        toast({ title: "验证码已发送", description: "请查收短信（B站）后输入。" })
        return
      }
      throw new Error(payload?.message || "滑块验证提交失败")
    } catch (err) {
      toast({ variant: "destructive", title: "补发失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  const handleSmsLogin = async () => {
    if (!smsCode.trim()) {
      toast({ variant: "destructive", title: "请输入验证码" })
      return
    }
    if (!smsToken) {
      toast({ variant: "destructive", title: "请先发送验证码" })
      return
    }
    try {
      await run("sms-confirm", () =>
        fetch(api("/sms/confirm"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sms_token: smsToken,
            code: smsCode.trim(),
            account_id: accountId,
          }),
        })
      )
      setPhase("done")
      resetSmsSession()
      toast({ variant: "success", title: "B站登录成功", description: "账号已绑定。" })
      onLoginDone?.()
    } catch (err) {
      toast({ variant: "destructive", title: "登录失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  // 账密登录：会话 + 极验 + 短信二次验证
  const [pwdToken, setPwdToken] = useState<string | null>(null)
  // need_captcha：geetest 内嵌上下文
  const [geetest, setGeetest] = useState<{
    gt?: string
    challenge?: string
    validate: string
    seccode: string
    showVerify: boolean
  } | null>(null)
  // need_sms：密码通过后短信二次验证码
  const [pwdSmsCode, setPwdSmsCode] = useState("")
  const [pwdNeedSms, setPwdNeedSms] = useState(false)

  const handlePasswordPrepare = async () => {
    if (!username.trim()) {
      toast({ variant: "destructive", title: "请输入账号" })
      return
    }
    try {
      const payload = await run("password-prepare", () =>
        fetch(api("/password/prepare"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim() }),
        })
      )
      if (payload?.pwd_token) {
        setPwdToken(payload.pwd_token)
        setPwdNeedSms(false)
        setPwdSmsCode("")
        setGeetest({ gt: payload?.geetest_gt ?? undefined, challenge: "", validate: "", seccode: "", showVerify: false })
        return payload
      }
      throw new Error(payload?.message || "登录会话建立失败")
    } catch (err) {
      toast({ variant: "destructive", title: "准备登录失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  const submitPassword = async (gi: { validate: string; seccode: string; challenge: string }) => {
    if (!pwdToken) {
      toast({ variant: "destructive", title: "请先准备登录会话" })
      return
    }
    if (!password) {
      toast({ variant: "destructive", title: "请输入密码" })
      return
    }
    try {
      const payload = await run("password-login", () =>
        fetch(api("/password"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pwd_token: pwdToken,
            password,
            challenge: gi.challenge ?? "",
            validate: gi.validate ?? "",
            seccode: gi.seccode ?? "",
            account_id: accountId,
          }),
        })
      )
      // need_captcha → 弹极验
      if (payload?.state === "need_captcha" && payload?.pwd_token) {
        setPwdToken(payload.pwd_token)
        setGeetest({
          gt: payload?.geetest_gt,
          challenge: payload?.geetest_challenge,
          validate: "",
          seccode: "",
          showVerify: true,
        })
        return
      }
      // need_sms → 进入短信二次验证
      if (payload?.state === "need_sms" && payload?.pwd_token) {
        setPwdToken(payload.pwd_token)
        setPwdNeedSms(true)
        setPwdSmsCode("")
        toast({ title: "需要短信验证", description: "密码已通过，请输入 B站 短信验证码完成登录。" })
        return
      }
      // success
      setPhase("done")
      resetSmsSession()
      toast({ variant: "success", title: "B站登录成功", description: "账号已绑定。" })
      onLoginDone?.()
    } catch (err) {
      toast({ variant: "destructive", title: "登录失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  // 内嵌极验：geetest 滑块点击完成后回调
  const handleGeetestDone = (validate: string, gchallenge: string) => {
    const seccode = `${validate}|jordan`
    const challenge = gchallenge || geetest?.challenge || geetest?.gt || ""
    setGeetest((prev) => (prev ? { ...prev, validate, seccode, showVerify: false } : prev))
    void submitPassword({ validate, seccode, challenge })
  }

  const handlePasswordLogin = async () => {
    // 首次点登录：先 prepare 建会话，再直接提交密码（无极验）
    if (!pwdToken) {
      const p = await handlePasswordPrepare()
      if (!p?.pwd_token) return
    }
    await submitPassword({ validate: "", seccode: "", challenge: "" })
  }

  const handlePwdSmsConfirm = async () => {
    if (!pwdToken) return
    if (!smsToken) {
      toast({ variant: "destructive", title: "请先发送短信验证码", description: "在「短信」Tab 对绑定手机号发送验证码后再确认。" })
      return
    }
    if (!pwdSmsCode.trim()) {
      toast({ variant: "destructive", title: "请输入短信验证码" })
      return
    }
    try {
      await run("password-sms-confirm", () =>
        fetch(api("/password/sms-confirm"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pwd_token: pwdToken, sms_token: smsToken, code: pwdSmsCode.trim(), account_id: accountId }),
        })
      )
      setPhase("done")
      setPwdNeedSms(false)
      toast({ variant: "success", title: "B站登录成功", description: "账号已绑定。" })
      onLoginDone?.()
    } catch (err) {
      toast({ variant: "destructive", title: "短信验证失败", description: err instanceof Error ? err.message : String(err) })
    }
  }

  void checkEnabled()

  return (
    <div className="rounded-2xl border border-border/70 bg-card p-4">
      {altEnabled === false && (
        <p className="mb-3 rounded-lg border border-border/60 bg-black px-3 py-2 text-[11px] text-muted-foreground">
          B站短信/账密登录已关闭：请在后端 .env 设置 <code className="font-mono">ALLOW_BILIBILI_ALT_LOGIN=true</code> 后重启；当前请使用上方「二维码登录」。
        </p>
      )}
      <Tabs defaultValue="sms">
        <TabsList className="grid w-full grid-cols-2 rounded-xl">
          <TabsTrigger value="sms" className="rounded-xl">
            <MessageSquareText className="mr-1 h-3.5 w-3.5" /> 短信
          </TabsTrigger>
          <TabsTrigger value="password" className="rounded-xl">
            <KeyRound className="mr-1 h-3.5 w-3.5" /> 账密
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sms" className="mt-3 space-y-3">
          <div className="grid grid-cols-[90px_1fr] gap-2">
            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground">区号</Label>
              <Input
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value.replace(/\D/g, ""))}
                className="bg-card/20 border-border/70 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground">手机号</Label>
              <Input
                placeholder="B站绑定手机号"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                className="bg-card/20 border-border/70 text-xs"
              />
            </div>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full"
            disabled={busyAction === "sms-send" || altEnabled === false}
            onClick={handleSendSms}
          >
            {busyAction === "sms-send" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            发送验证码
          </Button>

          {recaptchaUrl && (
            <div className="w-full">
              <p className="mb-1 flex items-center gap-1 text-[11px] font-medium text-amber-400">
                <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                需要滑块验证
              </p>
              {/* 内嵌 geetest：滑块通过后自动补发。裸放，避免任何外层定位/内边距干扰拖动 */}
              {smsGeetest?.showVerify ? (
                <GeetestEmbed
                  gt={smsGeetest.gt}
                  challenge={smsGeetest.challenge}
                  onDone={handleSmsGeetestDone}
                  onError={(m) => toast({ variant: "destructive", title: "滑块验证失败", description: m })}
                />
              ) : (
                <p className="text-[11px] text-amber-200/80">滑块已通过，正在补发…</p>
              )}
            </div>
          )}

          <div className="flex gap-2">
            <Input
              placeholder="短信验证码"
              value={smsCode}
              onChange={(e) => setSmsCode(e.target.value.replace(/\D/g, ""))}
              className="bg-card/20 border-border/70 text-xs"
            />
            <Button
              type="button"
              size="sm"
              className="shrink-0"
              disabled={busyAction === "sms-confirm" || !smsToken || !smsCode.trim()}
              onClick={handleSmsLogin}
            >
              {busyAction === "sms-confirm" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <KeyRound className="mr-1 h-3.5 w-3.5" />}
              登录
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="password" className="mt-3 space-y-3">
          <div className="space-y-1.5">
            <Label className="text-[10px] text-muted-foreground">B站账号（手机号/用户名）</Label>
            <Input
              placeholder="B站绑定手机号 / 用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="bg-card/20 border-border/70 text-xs"
              autoComplete="username"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-[10px] text-muted-foreground">密码</Label>
            <Input
              type="password"
              placeholder="B站登录密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-card/20 border-border/70 text-xs"
              autoComplete="current-password"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handlePasswordLogin()
              }}
            />
          </div>

          {/* need_sms：密码通过后短信二次验证 */}
          {pwdNeedSms && (
            <div className="space-y-2 rounded-xl border border-blue-500/40 bg-blue-500/10 p-3">
              <p className="flex items-center gap-1 text-[11px] font-medium text-blue-400">
                <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                密码已通过，需短信二次验证
              </p>
              <p className="text-[11px] leading-4 text-blue-200/70">
                请先到「短信」Tab 用绑定手机号发送验证码（若需滑块则在短信 Tab 完成），再回来填验证码确认。
              </p>
              <div className="flex gap-2">
                <Input
                  placeholder="B站短信验证码"
                  value={pwdSmsCode}
                  onChange={(e) => setPwdSmsCode(e.target.value.replace(/\D/g, ""))}
                  className="bg-card/20 border-border/70 text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  className="shrink-0"
                  disabled={busyAction === "password-sms-confirm" || !smsToken || !pwdSmsCode.trim()}
                  onClick={handlePwdSmsConfirm}
                >
                  {busyAction === "password-sms-confirm" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <KeyRound className="mr-1 h-3.5 w-3.5" />}
                  确认
                </Button>
              </div>
            </div>
          )}

          {/* need_captcha：内嵌 geetest 滑块。裸放，避免外层定位/内边距干扰拖动 */}
          {geetest?.showVerify && (
            <div className="w-full">
              <p className="mb-1 flex items-center gap-1 text-[11px] font-medium text-blue-400">
                <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                拖动滑块完成验证
              </p>
              <GeetestEmbed
                gt={geetest.gt ?? ""}
                challenge={geetest.challenge ?? ""}
                onDone={handleGeetestDone}
                onError={(m) =>
                  toast({ variant: "destructive", title: "滑块验证失败", description: m })
                }
              />
            </div>
          )}

          <Button
            type="button"
            size="sm"
            className="w-full"
            disabled={busyAction === "password-login" || busyAction === "password-prepare" || altEnabled === false}
            onClick={handlePasswordLogin}
          >
            {busyAction === "password-login" || busyAction === "password-prepare" ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <KeyRound className="mr-1 h-3.5 w-3.5" />
            )}
            账密登录
          </Button>
        </TabsContent>
      </Tabs>
    </div>
  )
}
