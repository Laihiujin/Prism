# Hermes 任务：打通"每平台专属发布配置"到各平台上传端

> 本文档是一份可直接交给 Hermes 执行的任务说明。目标不是造新功能，而是把
> **前端每个平台配置面板 → plan → 发布 payload → 后端任务 → 各平台上传器** 的链路真正打通，
> 并补齐目前**只有前端 UI、后端无实现**的那几个字段。

---

## 一、任务背景

Prism 是矩阵发布工具，前台每个平台（抖音/快手/小红书/B站/视频号）在
`prism_frontend/src/app/publish/components/PlatformConfigs.tsx` 里都有**独立配置面板**。
这些面板字段此前是**纯 UI**（本地 `useState`，提交即丢），现在要：
1. 让面板字段写回 plan（已完成，见下）。
2. 让发布任务真正**读取并按平台应用**这些配置。
3. 补齐后端没有实现的"可见性/保存权限/关联热点/合集/挂载游戏、小程序/横竖封面/封面文件/发布时机"等字段。

---

## 二、目前已完成（不要重复做，请在其基础上继续）

### 前端
- `PlatformConfigs.tsx`：新增 `usePlatformField(data,onChange,platform,key,initial)`，5 个面板
  （`DouyinConfig/KuaishouConfig/XhsConfig/BilibiliConfig/VideoChannelConfig`）的所有字段都改为
  **从 `plan.platformSettings[platform]` 读取、经 `onChange` 写回**（受控、可持久化）。
  - 存储键：`platformSettings.douyin / .kuaishou / .xiaohongshu / .bilibili / .channels`
  - 各平台字段（来自面板）：
    - douyin：`miniProgram{name,type}`、`poi{name,address}`、`coverOrientation`、`useAIRandomCover`、
      `coverFile`、`collection`、`declaration`、`hotspot`、`whoCanSee`、`savePermission`、`timing`、`publishDatetime`
    - kuaishou：`game{name,type}`、`poi{name,address}`
    - xiaohongshu：`poi{name,address}`
    - bilibili：`game{name,type}`、`tags`
    - channels：`article{title,date}`、`miniProgram{name,type}`、`location{name,address}`
- `matrix/page.tsx`：矩阵页**遍历已选平台**渲染 `renderPlatformConfig(platform)`；
  发布 payload 新增 **`platform_settings: plan.platformSettings`**；抖音顶层字段（declaration/location/random_cover/
  miniprogram_*）改从 `platformSettings.douyin` 取值。

### 后端（已加透传）
- `schemas/publish.py` `BatchPublishRequest`：新增 **`platform_settings: Optional[Dict[str, Any]]`**，
  兼容 `platform_settings` / `platformSettings`。
- `api/v1/publish/router.py`：`/batch` 与 `/single` 把 `request.platform_settings` 传给 service。
- `api/v1/publish/services.py`：把 `platform_settings` 透传进 `task_data["platform_settings"]`。

> 结论：**配置已经能从前端 → payload → 后端 `task_data`，不再被丢弃。** 断点在"任务执行端"。

---

## 三、真正的断点 / 缺口（这是本次要做的）

### 断点①：`myUtils/batch_publish_service.py` 没解包 `platform_settings`
`handle_single_publish(self, data)`（**第 38 行**）把 `task_data` 拉成**固定扁平参数**调
`uploader.upload(...)`（**第 107 行**），例如 `location=data.get("location")`、`declaration=data.get("declaration")`。
它**没有读 `data.get("platform_settings")`**，所以快手/小红书等平台配置到不了上传器。

需要在这里：取 `ps = (data.get("platform_settings") or {}).get(<平台key>, {})`，并把字段合并进
`uploader.upload(...)` 调用。

**平台 code → platform_settings key 映射**（见 `platforms/registry.py` 第 30-39 行）：
```
1 → "xiaohongshu"
2 → "channels"   # 视频号（registry 内部模块为 platforms.tencent）
3 → "douyin"
4 → "kuaishou"
5 → "bilibili"
6 → "tiktok"
7 → "youtube"
8 → "baijiahao"
```

### 断点②：各平台上传器 `upload()` 不认得这些字段（应用层缺失）
| 平台 | 上传器 | upload() 已认得 |
|---|---|---|
| 抖音 | `platforms/douyin/upload.py` | `location, declaration, random_cover, miniprogram_link, miniprogram_title, product_link, product_title, category_id` |
| 快手 | `platforms/kuaishou/upload.py` | `account_file,title,file_path,tags,publish_date,description,**kwargs` |
| 小红书 | `platforms/xiaohongshu/upload.py` | `account_file,title,file_path,tags,publish_date,thumbnail_path,description,**kwargs` |
| B站 | `platforms/bilibili/upload.py` | `account_file,title,file_path,tags,publish_date,category_id,description,**kwargs` |
| 视频号 | `platforms/tencent/upload.py` | `**kwargs` |

### 断点③：以下 9 个前端字段在后端**从未实现**（`git log -S` 全历史均无命中）
`whoCanSee`(谁可以看)、`savePermission`(保存权限)、`hotspot`(关联热点)、
`collection`(合集下拉，抖音)、`game`(挂载游戏/应用)、`miniProgram`(当作"挂载对象"选择用)、
`coverOrientation`(横/竖封面)、`coverFile`(封面文件)、`timing/publishDatetime`(发布时机)。

> 其中 `coverOrientation/coverFile/timing` 和 `declaration/location/random_cover/miniprogram_*`
> 抖音侧**已有部分对应**（见下表）。真正完全没有的是 `whoCanSee/savePermission/hotspot/collection/game/miniProgram`。

---

## 四、抖音上传器（主战场）：功能 → 具体代码位置

文件：`prism_backend/uploader/douyin_uploader/main_refactored.py`（`main()` 主流程的 `upload()` 在**第 935 行**）。这些功能**已实现**，可作为"已落地字段"的参考/模板：

| 功能 | 方法 | 行号 |
|---|---|---|
| 话题补全精确选择 | `_select_topic_exact` | 359 |
| 版本提示遮挡清理 | `dismiss_version_prompt` | 562 |
| 定位权限 | `set_location` / `_handle_browser_permission` | 386 / 585 |
| 随机封面 | `handle_auto_video_cover` | 768 |
| 封面上传 | `set_thumbnail` / `_handle_cover_recommend_modal` / `_force_close_cover_modal` | 830 / 793 / 894 |
| 自主声明 | `set_self_declaration` / `apply_self_declaration` | 469 / 715 |
| 小程序链接 | `set_miniprogram_link` | 631 |

主 `upload()` 里的调用顺序（**第 995-1051 行**）：话题 → 商品 → 小程序 → 定位/权限 → 封面 → 自主声明 → 定时。

---

## 五、本次要执行的任务（按优先级）

### P0：打通"ps → uploader"（必做）
在 `handle_single_publish`（`batch_publish_service.py` 第 107 行处）按平台 code 取 `ps`，并合并进
`uploader.upload(...)`：
```python
ps = (data.get("platform_settings") or {}).get(PLATFORM_KEY_BY_CODE.get(platform), {}) or {}
# 示例（所有平台通用/可落地项）
location = data.get("location") or (ps.get("poi") or {}).get("name", "") or (ps.get("location") or {}).get("name", "")
declaration = data.get("declaration") or ps.get("declaration", None)
random_cover = data.get("random_cover") or bool(ps.get("useAIRandomCover", False))
miniprogram_link = data.get("miniprogram_link") or ""
miniprogram_title = data.get("miniprogram_title") or ""
```
保持抖音现有行为不变（前端已把 `platformSettings.douyin` 映射到顶层字段，所以抖音要么继续走顶层、要么从 `ps.douyin` 取，二选一即可，勿重复/冲突）。

### P1：给各平台上传器补字段（在各自 `upload()`/底层类里读并应用）
- **快手** `kuaishou/upload.py`（底层 `uploader.ks_uploader.main.KSVideo`）：接 `poi→location`、`game`（挂载游戏/应用）。
- **小红书** `xiaohongshu/upload.py`：接 `poi→location`。
- **视频号** `tencent/upload.py`：接 `location`、`miniProgram`、`article`（公众号文章）。
- **B站** `bilibili/upload.py`：接 `game`、`tags`。

### P2：抖音侧补齐目前无实现的字段（需要实测 DOM，谨慎）
`whoCanSee`、`savePermission`、`hotspot`、`collection` 这 4 个字段的发布端逻辑，接口路径可参考
现有 `set_self_declaration`/`set_thumbnail`/`_handle_browser_permission` 的手法。

---

## 六、验收标准
1. 前端选中多个平台并配置面板 → 提交后，后端 `task_data["platform_settings"]` 能拿到对应平台的值。
2. `handle_single_publish` 能按平台把配置传给 `uploader.upload(...)`。
3. 各平台上传器确实应用了能落地的字段（至少 `location` 在快手/小红书生效）。
4. 抖音既有 7 个功能回归不坏（话题/版本/定位/随机封面/封面/自主声明/小程序）。

## 七、注意事项
- **不要动** `prism_backend/uploader/douyin_uploader/main_refactored.py` 里已有的 e205652 逻辑（除非加新字段）。
- `platform_settings` 是后端新增字段，`BatchPublishRequest` 已支持；**不要**改它的语义，保持"key=平台代码"。
- 改动后端前先跑 `python -c "import ast; ast.parse(open(f).read())"` 校验语法。
- 发布链路相关文件不要跑到前端工具目录；`prism_cli.py`、`AGENTS.md` 为既有工程约束，遵循之。
