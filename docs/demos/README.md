# Prism 产品演示视频

本目录存放 Prism 产品演示的最终成品(纯黑白)。

| 文件 | 说明 | 规格 |
|---|---|---|
| `prism_demo.mp4` | 14 页功能巡览(仪表盘 / 账号管理 / 素材 / 代理 / 矩阵发布 / 任务 / 数据 / Agent / 工具 / 设置 …) | 1280×720 · 24fps · 32s |
| `prism_hyperframes_demo.gif` | 同上,循环 GIF | 720×405 · 256 帧 · 循环 |
| `prism_wrap.mp4` | 真实交互 walkthrough(登录弹窗 / Agent 对话),Apple 质感包装(标题卡 + 页面字幕 + 段间转场) | 1280×720 · 24fps · 47.75s |
| `prism_wrap.gif` | 同上,循环 GIF | 720×405 · 382 帧 · 循环 |

- 均由 HyperFrames 确定性合成(SMPTE 帧级寻址,`window.__timelines["master"]` 驱动)。
- 统一 **纯黑白** 风格(灰度,`hue=s=0`),Apple 冷调玻璃质感(仅 `prism_wrap`)。
- 账号管理场景使用「账户页实拍」图片(含 7 平台账号),作为宣传展示,未做脱敏。

## 生成与再生成
源合成与脚本在 `output/hf-prism/`:
- `prism-demo/gen_composition.py` -> 14 页图片巡览合成(`prism_demo`),截图为 `output/shots/*.png`。
- `prism-wrap/index.html` -> 真实交互 walkthrough 叠加标题/字幕/转场(`prism_wrap`),底图为 `output/prism_walkthrough.mp4`。

再生成示例:
```bash
bash output/hf-prism/render_demo_v2.sh     # 重渲 prism_demo(b/w, 无模糊)
bash output/hf-prism/render_final_wrap.sh  # 重渲 prism_wrap
```

> 注意:仓库 `.gitignore` 忽略 `*.mp4`,故本目录的 MP4 需用 `git add -f` 强制跟踪;GIF 可正常跟踪。
