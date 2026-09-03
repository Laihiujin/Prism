# Prism 产品演示视频

本目录存放 Prism 产品演示的最终成品(纯黑白)。

| 文件 | 说明 | 规格 |
|---|---|---|
| `prism_demo.mp4` | 14 页功能巡览(仪表盘 / 账号管理 / 素材 / 代理 / 矩阵发布 / 任务 / 数据 / Agent / 工具 / 设置 …) | 1280×720 · 24fps · 32s |
| `prism_hyperframes_demo.gif` | 同上,循环 GIF | 720×405 · 256 帧 · 循环 |
| `prism_wrap.mp4` | 真实交互 walkthrough(登录弹窗 / Agent 对话),纯黑白包装(标题卡 + 页面字幕 + 段间转场),基于新 UI 录屏 | 1280×720 · 24fps · 59.4s |
| `prism_wrap.gif` | 同上,循环 GIF(包装版,README 推荐使用) | 720×405 · 475 帧 · 循环 |
| `prism_walkthrough.gif` | 同一交互的**原始录屏** GIF(无标题/字幕/转场叠加) | 720×405 · 475 帧 · 循环 |

- 均由 HyperFrames 确定性合成(SMPTE 帧级寻址,`window.__timelines["master"]` 驱动)。
- 统一 **纯黑白** 单色风格:黑底 + 白色文字/高光,仅用中性灰做层次,无任何彩色;标题/页码用白色→浅灰渐变,配淡白辉光与细网格(动画用 HyperFrames 支持的 opacity/x/y/scale/width 属性 + expo/back 缓动,含图片 Ken Burns)。
- 账号管理场景使用「账户页实拍」图片(含 7 平台账号),作为宣传展示,未做脱敏。
- walkthrough 为真实交互录屏:账号登录弹窗(添加账号 → 选抖音 → 扫码)+ Hermes Agent 终端实时对话;背景视频已灰度化以保持纯黑白。

## 生成与再生成
源合成与脚本在 `output/hf-prism/`:
- `prism-demo/gen_composition.py` -> 14 页图片巡览合成(`prism_demo`),截图为 `output/shots/*.png`。
- `prism-wrap/index.html` -> 真实交互 walkthrough 叠加标题/字幕/转场(`prism_wrap`),底图为 `output/prism_walkthrough.mp4`。
- `output/walkthrough/capture_walkthrough_new.py` -> 重录新 UI 交互录屏(`output/prism_walkthrough.mp4`)。

再生成示例:
```bash
bash output/hf-prism/render_demo_v3.sh     # 重渲 prism_demo(纯黑白, 无彩色/无模糊)
bash output/hf-prism/render_final_wrap.sh  # 重渲 prism_wrap
```

> 注意:仓库 `.gitignore` 忽略 `*.mp4`,故本目录的 MP4 需用 `git add -f` 强制跟踪;GIF 可正常跟踪。
