# Prism 与宿主工具适配

## 发现能力

读取项目工具目录/CLI/MCP schema，避免按技能名称臆造 API。Prism 现有入口：
- generate_cover(file_id, platform_name, aspect_ratio, prompt, style_hint, use_first_frame) 返回job_id。
- get_cover_job(job_id) 查询成功/失败与实际路径。
- list_material_covers(file_id)，select_material_cover(file_id, cover_id)。
- adapt_material_cover(file_id, path, platform)，path 是素材库相对路径。
CLI：`python prism_cli.py tool invoke <工具名> --json-file <参数文件>`。

当前 generate_cover 比例仅 3:4 / 4:3；use_first_frame 仅视频首帧，不等于任意本地产品或 Logo 引用。它没有原始产品图列表参数。遇到需要原图参考的品牌生图，使用宿主实际支持的参考图片生成/编辑入口；不要用不支持的 Prism 参数或偷偷退回纯文生图。

## 工具选择

用户指定提供者优先。否则使用宿主当前可用图像工具与其技能；支持本地图像引用时原图直接传入，上传式工具按文档获取素材标识并记录原文件对应关系。不要擅自安装模型后端、换付费服务或要求用户提供不需要的密钥。
没有所需能力时交付准备好的方案、素材清单和提示词并说明阻断，不能说成已出图。工具比例与最终发布器不同时先解决裁切/重排，不拉伸图像。

## 发现与兼容

Prism 维护源位于 docs/hermes-skills/prism-cover-studio/，会话准备同步至 Hermes creative 分类的同名目录。旧 prism-title-topic 与 prism-social-content 路由到本入口；独立仓库仅需安装本技能，全部必要参考在内部。
生成和选用不等于发布。实际发布继续使用对应平台发布技能和用户明确授权。
