"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, QrCode, RefreshCcw } from "lucide-react";
import { backendBaseUrl } from "@/lib/env";
import { fetcher } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BrowserViewport } from "@/components/account/remote-login-view";

const platforms: Record<string, string> = {
  douyin: "抖音",
  kuaishou: "快手",
  tencent: "视频号",
  xiaohongshu: "小红书",
  bilibili: "B站",
  tiktok: "TikTok",
  youtube: "YouTube",
};
const stateLabels: Record<string, string> = {
  active: "分发中",
  stopped: "已停止",
  completed: "领取完成",
  expired: "已到期",
  pending: "等待启动",
  waiting: "等待登录",
  scanned: "已扫码",
  confirmed: "登录成功",
  failed: "失败",
  error: "连接异常",
  risk_control: "等待人工验证",
  cooldown: "刷新冷却中",
  ready: "待执行",
  submitting: "正在提交",
  queued: "已提交",
  needs_review: "待核对",
};
type Material = {
  id: string | number;
  name?: string;
  filename?: string;
  type?: string;
};
type Preset = {
  name: string;
  platform: string;
  data?: {
    form?: { title?: string; tags?: string | string[]; cover_image?: string };
  };
};
type Schedule = {
  schedule_type: "immediate" | "scheduled";
  scheduled_time: string | null;
  interval_seconds: number;
  item_count: number;
};
type Package = {
  error?: string;
  id: string;
  platform: string;
  account_id: string;
  schedule: Schedule;
  items: {
    file_id: number;
    title: string;
    scheduled_time: string | null;
    status: string;
    error?: string;
    result?: { tasks?: { task_id: string }[] };
  }[];
};
type Lane = {
  status: string;
  session_id: string | null;
  qr_image: string | null;
  qr_expires_at?: number;
  next_refresh_at: number;
  completed: number;
  error?: string;
};
type Task = {
  id: string;
  name: string;
  status: string;
  materials: { file_id: number }[];
  config: { accounts_per_platform: number; auto_publish: boolean };
  lanes: Record<string, Lane>;
  packages: Package[];
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${backendBaseUrl}/api/v1${path}`, {
    cache: "no-store",
    ...(body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
  });
  const payload = await response.json();
  if (!response.ok || payload.success === false)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : payload.message || `请求失败 (${response.status})`,
    );
  return payload.data as T;
}

const selectClass =
  "h-10 w-full rounded-md border border-border bg-background px-3 text-sm";
function localTime(value: string | null) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return new Date(d.getTime() + 8 * 3600000).toISOString().slice(0, 16);
}
function timeLabel(value: number) {
  return new Date(value * 1000).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
  });
}

function PackageEditor({
  taskId,
  pack,
  onChanged,
  now,
}: {
  taskId: string;
  pack: Package;
  onChanged: () => void;
  now: number;
}) {
  const ready = pack.items.filter((item) => item.status === "ready").length;
  const [schedule, setSchedule] = useState<Schedule>({
    ...pack.schedule,
    item_count: Math.min(pack.schedule.item_count || ready, ready),
  });
  const mutation = useMutation({
    mutationFn: (action: "configure" | "publish") =>
      api(`/tasks/distribution/${taskId}/action`, {
        action,
        package_id: pack.id,
        schedule,
      }),
    onSuccess: onChanged,
  });
  const start =
    schedule.schedule_type === "scheduled"
      ? Date.parse(schedule.scheduled_time || "")
      : now;
  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="text-base">
          {platforms[pack.platform]} · {pack.account_id}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {pack.error && (
          <p role="alert" className="text-sm text-destructive">
            {pack.error}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {pack.items.length} 条素材 · {ready}{" "}
          条待执行。修改只作用于待执行条目。
        </p>
        {ready > 0 && (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Label className="space-y-2">
                执行方式
                <select
                  className={selectClass}
                  value={schedule.schedule_type}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      schedule_type: e.target
                        .value as Schedule["schedule_type"],
                    })
                  }
                >
                  <option value="immediate">立即开始</option>
                  <option value="scheduled">定时开始</option>
                </select>
              </Label>
              <Label className="space-y-2">
                本次发布数量
                <Input
                  type="number"
                  min={1}
                  max={ready}
                  value={schedule.item_count}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      item_count: Number(e.target.value),
                    })
                  }
                />
              </Label>
              <Label className="space-y-2">
                间隔（分钟）
                <Input
                  type="number"
                  min={1}
                  max={1440}
                  step="any"
                  value={schedule.interval_seconds / 60}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      interval_seconds: Math.round(Number(e.target.value) * 60),
                    })
                  }
                />
              </Label>
              <Label className="space-y-2">
                每日频率（条）
                <Input
                  type="number"
                  min={1}
                  max={1440}
                  value={Math.round(86400 / schedule.interval_seconds)}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      interval_seconds: Math.max(
                        60,
                        Math.round(86400 / Math.max(1, Number(e.target.value))),
                      ),
                    })
                  }
                />
              </Label>
            </div>
            {schedule.schedule_type === "scheduled" && (
              <Label className="block space-y-2">
                首条发布时间（北京时间）
                <Input
                  type="datetime-local"
                  value={localTime(schedule.scheduled_time)}
                  onChange={(e) =>
                    setSchedule({
                      ...schedule,
                      scheduled_time: e.target.value
                        ? `${e.target.value}:00+08:00`
                        : null,
                    })
                  }
                />
              </Label>
            )}
            <p className="text-xs text-muted-foreground">
              频率按均匀间隔换算；本次只发布所选数量，剩余素材保留待执行。
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate("configure")}
              >
                保存安排，暂不执行
              </Button>
              <Button
                disabled={
                  mutation.isPending ||
                  schedule.item_count < 1 ||
                  schedule.item_count > ready ||
                  !Number.isFinite(start)
                }
                onClick={() => mutation.mutate("publish")}
              >
                {schedule.schedule_type === "immediate"
                  ? "立即执行所选数量"
                  : "提交定时发布"}
              </Button>
            </div>
          </>
        )}
        {mutation.error && (
          <p role="alert" className="text-sm text-destructive">
            {mutation.error.message}
          </p>
        )}
        <ol className="space-y-2 text-sm">
          {pack.items.map((item, i) => {
            const pendingIndex = pack.items
              .slice(0, i)
              .filter((x) => x.status === "ready").length;
            const included =
              item.status === "ready" && pendingIndex < schedule.item_count;
            const preview =
              included && Number.isFinite(start)
                ? new Date(
                    start + pendingIndex * schedule.interval_seconds * 1000,
                  ).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })
                : item.scheduled_time
                  ? new Date(item.scheduled_time).toLocaleString("zh-CN", {
                      timeZone: "Asia/Shanghai",
                    })
                  : "";
            return (
              <li
                key={item.file_id}
                className="rounded border border-border p-3"
              >
                <span>{item.title}</span>{" "}
                <Badge variant="secondary">
                  {stateLabels[item.status] || item.status}
                </Badge>
                <p className="mt-1 text-xs text-muted-foreground">
                  {included
                    ? `本次预计：${preview}`
                    : item.status === "ready"
                      ? "保留到下次执行"
                      : preview}
                  {item.error && ` · ${item.error}`}
                </p>
              </li>
            );
          })}
        </ol>
        <Link href="/tasks" className="text-sm underline">
          查看发布进度及待核对任务
        </Link>
      </CardContent>
    </Card>
  );
}

export default function QRDistributionPage() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [remote, setRemote] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [targets, setTargets] = useState<string[]>(["douyin"]);
  const [selected, setSelected] = useState<number[]>([]);
  const [bindings, setBindings] = useState<
    Record<number, Record<string, string>>
  >({});
  const [allocation, setAllocation] = useState("one_per_account");
  const [accounts, setAccounts] = useState(1);
  const [automatic, setAutomatic] = useState(false);
  const [scheduleType, setScheduleType] = useState("immediate");
  const [scheduledTime, setScheduledTime] = useState("");
  const [interval, setIntervalSeconds] = useState(600);
  const tasks = useQuery({
    queryKey: ["qr-distributions"],
    queryFn: () => api<Task[]>("/tasks/distribution"),
    refetchInterval: 5000,
  });
  const materialsQuery = useQuery({
    queryKey: ["distribution-materials"],
    queryFn: () =>
      fetcher<Material[] | { items?: Material[]; data?: Material[] }>(
        "/api/materials?page_size=100",
      ),
  });
  const materialsData = materialsQuery.data;
  const materials = Array.isArray(materialsData)
    ? materialsData
    : materialsData?.items || materialsData?.data || [];
  const presets = useQuery({
    queryKey: ["distribution-presets", selected],
    enabled: selected.length > 0,
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          selected.map(async (id) => [
            id,
            await api<Record<string, Preset>>(`/files/${id}/presets`),
          ]),
        ),
      ) as Record<number, Record<string, Preset>>,
  });
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["qr-distributions"] });
  };
  const create = useMutation({
    mutationFn: () =>
      api<Task>("/tasks/distribution", {
        name,
        platforms: targets,
        materials: selected.map((file_id) => ({
          file_id,
          presets: bindings[file_id] || {},
        })),
        accounts_per_platform: accounts,
        allocation,
        auto_publish: automatic,
        schedule_type: scheduleType,
        scheduled_time:
          scheduleType === "scheduled" && scheduledTime
            ? `${scheduledTime}:00+08:00`
            : null,
        interval_seconds: interval,
        expires_hours: 24,
      }),
    onSuccess: (task) => {
      setCreating(false);
      setSelectedTask(task.id);
      invalidate();
    },
  });
  const action = useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      action: string;
      platform?: string;
    }) => api(`/tasks/distribution/${id}/action`, body),
    onSuccess: invalidate,
  });
  const current = tasks.data?.find((t) => t.id === selectedTask);
  const remoteSession = tasks.data?.some((task) =>
    Object.values(task.lanes).some((lane) => lane.session_id === remote),
  )
    ? remote
    : null;
  const canCreate =
    name.trim() &&
    selected.length > 0 &&
    targets.length > 0 &&
    selected.every((id) => targets.every((p) => bindings[id]?.[p])) &&
    (allocation !== "one_per_account" || accounts <= selected.length);
  const summary = useMemo(
    () => ({
      active: tasks.data?.filter((t) => t.status === "active").length || 0,
      packages: tasks.data?.reduce((sum, t) => sum + t.packages.length, 0) || 0,
    }),
    [tasks.data],
  );

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <QrCode />
            扫码分发
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            素材绑定平台预设 → 独立浏览器登录 → 账号任务包 → 立即或定时发布
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          新建扫码分发
        </Button>
      </div>
      <div className="rounded-xl border border-border bg-card p-4 text-sm">
        <p>
          {summary.active} 个任务分发中 · 已生成 {summary.packages} 个账号任务包
        </p>
        <p className="mt-2 text-muted-foreground">
          每个平台使用独立登录会话，任何成功登录的账号都可领取。预设在创建时固定；关闭此页后后台继续处理。自动刷新至少间隔10分钟，逐次延长至2小时，每个登录会话滚动24小时最多12次；人工验证期间保留原页面。
        </p>
      </div>
      {(tasks.error || action.error) && (
        <p role="alert" className="text-destructive">
          {(tasks.error || action.error)?.message}
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>任务 / 素材</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>账号任务包</TableHead>
              <TableHead>操作</TableHead>
              <TableHead>二维码扫码派发</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.isLoading && (
              <TableRow>
                <TableCell colSpan={5}>正在加载…</TableCell>
              </TableRow>
            )}
            {tasks.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  还没有分发任务。先在素材管理保存平台预设，再创建分发。
                </TableCell>
              </TableRow>
            )}
            {tasks.data?.map((task) => (
              <TableRow key={task.id}>
                <TableCell>
                  <p className="font-medium">{task.name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {task.materials.length} 条素材 ·{" "}
                    {task.config.auto_publish
                      ? "领取后自动执行"
                      : "领取后待执行"}
                  </p>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{stateLabels[task.status]}</Badge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="link"
                    onClick={() => setSelectedTask(task.id)}
                  >
                    {task.packages.length} 个 · 查看安排
                  </Button>
                </TableCell>
                <TableCell>
                  {task.status === "active" && (
                    <Button
                      variant="outline"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: task.id, action: "stop" })
                      }
                    >
                      停止接收登录
                    </Button>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-4">
                    {Object.entries(task.lanes).map(([platform, lane]) => (
                      <div
                        key={platform}
                        className="w-44 space-y-2 rounded-lg border border-border p-3"
                      >
                        <p className="text-sm font-medium">
                          {platforms[platform]} {lane.completed}/
                          {task.config.accounts_per_platform}
                        </p>
                        <p className="text-xs">
                          {stateLabels[lane.status] || lane.status}
                        </p>
                        {lane.qr_image &&
                          !["tiktok", "youtube"].includes(platform) && (
                            <img
                              src={lane.qr_image}
                              width={144}
                              height={144}
                              alt={`${platforms[platform]}登录二维码`}
                              className="rounded bg-white p-2"
                            />
                          )}
                        <p className="text-xs text-muted-foreground">
                          {lane.qr_expires_at &&
                          lane.session_id &&
                          lane.qr_expires_at < now / 1000
                            ? "二维码显示期已过，等待冷却后刷新"
                            : ""}
                        </p>
                        {lane.error && (
                          <p role="alert" className="text-xs text-destructive">
                            {lane.error}
                          </p>
                        )}
                        {lane.session_id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setRemote(lane.session_id)}
                          >
                            打开登录网页
                          </Button>
                        )}
                        {task.status === "active" &&
                          lane.completed <
                            task.config.accounts_per_platform && (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={
                                  action.isPending ||
                                  lane.next_refresh_at > now / 1000
                                }
                                onClick={() =>
                                  action.mutate({
                                    id: task.id,
                                    action: "refresh",
                                    platform,
                                  })
                                }
                              >
                                <RefreshCcw className="mr-1 h-3 w-3" />
                                刷新登录
                              </Button>
                              {lane.next_refresh_at > now / 1000 && (
                                <p className="text-xs text-muted-foreground">
                                  可刷新：{timeLabel(lane.next_refresh_at)}
                                </p>
                              )}
                            </>
                          )}
                      </div>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>新建扫码分发</DialogTitle>
            <DialogDescription>
              选择素材和已保存的各平台预设。自动执行可跳过，派发后再调整数量、间隔和定时。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-5">
            <Label className="block space-y-2">
              任务名称
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Label>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">目标平台</legend>
              <div className="flex flex-wrap gap-4">
                {Object.entries(platforms).map(([p, label]) => (
                  <label key={p} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={targets.includes(p)}
                      onChange={(e) =>
                        setTargets(
                          e.target.checked
                            ? [...targets, p]
                            : targets.filter((x) => x !== p),
                        )
                      }
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="space-y-3">
              <p className="text-sm font-medium">视频素材及平台预设</p>
              <Link href="/materials/videos" className="text-xs underline">
                前往素材管理配置标题、标签和封面预设
              </Link>
              {materialsQuery.isLoading && (
                <p className="text-sm">正在加载素材…</p>
              )}
              {materialsQuery.error && (
                <p role="alert">{materialsQuery.error.message}</p>
              )}
              {materials
                .filter((m) => m.type === "video")
                .map((material) => {
                  const id = Number(material.id);
                  return (
                    <div
                      key={id}
                      className="space-y-3 rounded border border-border p-3"
                    >
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={selected.includes(id)}
                          onChange={(e) =>
                            setSelected(
                              e.target.checked
                                ? [...selected, id]
                                : selected.filter((x) => x !== id),
                            )
                          }
                        />
                        {material.name || material.filename || id}
                      </label>
                      {selected.includes(id) &&
                        targets.map((p) => {
                          const key = p === "tencent" ? "wechat" : p;
                          const available = Object.entries(
                            presets.data?.[id] || {},
                          ).filter(
                            ([, v]) =>
                              v.platform === "all" || v.platform === key,
                          );
                          return (
                            <Label key={p} className="block space-y-1">
                              {platforms[p]} 预设
                              <select
                                className={selectClass}
                                value={bindings[id]?.[p] || ""}
                                onChange={(e) =>
                                  setBindings({
                                    ...bindings,
                                    [id]: {
                                      ...bindings[id],
                                      [p]: e.target.value,
                                    },
                                  })
                                }
                              >
                                <option value="">
                                  {presets.isLoading
                                    ? "正在加载预设…"
                                    : available.length
                                      ? "选择已保存的预设"
                                      : "请先为此素材保存平台预设"}
                                </option>
                                {available.map(([presetId, preset]) => (
                                  <option key={presetId} value={presetId}>
                                    {preset.name} ·{" "}
                                    {preset.data?.form?.title || "标题未填写"}
                                  </option>
                                ))}
                              </select>
                            </Label>
                          );
                        })}
                    </div>
                  );
                })}
              {presets.error && (
                <p role="alert" className="text-destructive">
                  {presets.error.message}
                </p>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Label className="space-y-2">
                素材分配方式
                <select
                  className={selectClass}
                  value={allocation}
                  onChange={(e) => setAllocation(e.target.value)}
                >
                  <option value="one_per_account">每个账号依次领取一条</option>
                  <option value="all_per_account">每个账号领取整组素材</option>
                </select>
              </Label>
              <Label className="space-y-2">
                每个平台接收账号数
                <Input
                  type="number"
                  min={1}
                  max={
                    allocation === "one_per_account"
                      ? selected.length || 1
                      : 100
                  }
                  value={accounts}
                  onChange={(e) => setAccounts(Number(e.target.value))}
                />
              </Label>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={automatic}
                onChange={(e) => setAutomatic(e.target.checked)}
              />
              登录成功后自动执行（可跳过）
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <Label className="space-y-2">
                默认发布方式
                <select
                  className={selectClass}
                  value={scheduleType}
                  onChange={(e) => setScheduleType(e.target.value)}
                >
                  <option value="immediate">立即开始</option>
                  <option value="scheduled">定时开始</option>
                </select>
              </Label>
              <Label className="space-y-2">
                默认间隔（分钟）
                <Input
                  type="number"
                  min={1}
                  max={1440}
                  value={interval / 60}
                  onChange={(e) =>
                    setIntervalSeconds(Math.round(Number(e.target.value) * 60))
                  }
                />
              </Label>
            </div>
            {scheduleType === "scheduled" && (
              <Label className="block space-y-2">
                首条发布时间（北京时间）
                <Input
                  type="datetime-local"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                />
              </Label>
            )}
            {create.error && (
              <p role="alert" className="text-destructive">
                {create.error.message}
              </p>
            )}
            <Button
              disabled={!canCreate || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? "正在创建…" : "创建分发并准备登录"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!current}
        onOpenChange={(open) => {
          if (!open) setSelectedTask(null);
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{current?.name} · 账号任务包</DialogTitle>
            <DialogDescription>
              按数量、间隔或每日频率调整待执行素材，先保存安排或直接提交。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {!current?.packages.length && (
              <p className="text-sm text-muted-foreground">
                等待平台登录成功后生成任务包。
              </p>
            )}
            {current?.packages.map((pack) => (
              <PackageEditor
                key={`${pack.id}:${pack.items.map((i) => i.status).join(",")}`}
                taskId={current.id}
                pack={pack}
                onChanged={invalidate}
                now={now}
              />
            ))}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!remoteSession}
        onOpenChange={(open) => {
          if (!open) setRemote(null);
        }}
      >
        <DialogContent className="max-h-[95vh] max-w-6xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>平台授权登录</DialogTitle>
            <DialogDescription>
              在此窗口完成平台登录及确认。登录成功后绑定当前账号并生成素材任务包。
            </DialogDescription>
          </DialogHeader>
          {remoteSession && (
            <BrowserViewport key={remoteSession} sessionId={remoteSession} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
