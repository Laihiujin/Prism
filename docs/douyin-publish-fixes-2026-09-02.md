# 抖音发布链路修复记录（2026-09-02）

> 本次按 `docs/hermes-skills/douyin-publish-computeruse/SKILL.md`（skill）与
> `docs/douyin-publish-features.md`（DOM 规格）验证抖音发布链路时，发现并修复了
> **2 个真实 bug**，并完成一次真实发布。

---

## ✅ 改动文件（2 处修复）

### 1. `prism_backend/uploader/douyin_uploader/main_refactored.py` — 话题校验误判
**问题**：`fill_title_and_description()` 校验话题时用 `current_text.rstrip().endswith(expected_topic)`。
抖音富文本编辑器会在话题节点后**自动附加零宽空格 `\u200b`**，`rstrip()` 去不掉它，
导致 `'#Seedance25\u200b'.endswith('#Seedance25')` 为 `False`，误判「话题未完整输入」并中断发布。
（preview 时实际报错：`expected='#Seedance25', actual='#Seedance25\u200b'`）

**修复**：校验前先去零宽/不可见字符（U+200B–200D、FEFF、2060、NBSP），再 `endswith`。
```python
_norm = "".join(
    ch for ch in current_text
    if not (0x200B <= ord(ch) <= 0x200D) and ch not in "\ufeff\u2060\xa0"
).rstrip()
if not _norm.endswith(expected_topic):
    raise RuntimeError(...)
```

### 2. `prism_backend/platforms/douyin/upload.py` — 封面弹窗残留遮挡发布按钮
**问题**：`_set_thumbnail_best_effort()` 用**哈希 class**（`primary-RstHX_` / `secondary-zU1YLr`）
点「完成」关闭封面弹窗——CSS-Module 哈希名随版本变化，在新版发布页点不中，
封面编辑弹窗（`canvas.upper-canvas.cloudImage`，位于 `dy-creator-content-portal`）残留，
**pointer-events 拦截发布按钮** → `_publish_video` 点击发布 60s 超时。

**修复**（两处）：
1. `_set_thumbnail_best_effort()`：哈希点击失败时，改用**文本语义**兜底点「完成/确定/保存」。
2. `_publish_video()`：点发布前先 `_wait_cover_modal_closed()`（semantic），
   若仍失败则强制移除 `dy-creator-content-modal-wrap / dy-creator-content-modal /
   dy-creator-content-portal / canvas.upper-canvas.cloudImage`。

---

## 验证结果

| 步骤 | 结果 |
|---|---|
| 4 个输入文件语法 `ast.parse` | ✅ 通过 |
| preview（`DouYinVideo`，跑完整流程，停在发布前） | ✅ 4 个话题贴上；自主声明「内容由AI生成」生效；未真发 |
| **真实发布**（`handle_single_publish` → `DouyinUpload`） | ✅ **成功**，`published_at=2026-09-02T21:16:15+08:00` |

**已发布内容**：素材 id=3 `60d455f2-...MP4`（Seedance 2.5 AIGC 视频）
- 标题：`Seedance 2.5 视频生成实测,这画质我服了`
- 标签：`Seedance25 / AIGC / AI视频生成 / AI创作`
- 发布到抖音账号「门」（`account_1788171770695`）

---

## ⚠️ 遗留
- 后端 FastAPI + Celery 仍运行旧代码。**通过 API /batch 触发发布需重启后端**才能加载上述修复
  （本次为源码加载直接运行，已验证）。
- `platform_settings.douyin` 的新字段（whoCanSee/savePermission/hotspot/collection/
  miniProgram/coverOrientation）为 best-effort 透传；`whoCanSee=公开`、`savePermission=允许`
  时按默认值跳过，不额外触发。
