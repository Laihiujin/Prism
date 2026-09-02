# Prism 产品演示视频

本目录存放 Prism 产品演示的最终成品(暗黑科技风)。

| 文件 | 说明 | 规格 |
|---|---|---|
| `prism_demo.mp4` | 14 页功能巡览(仪表盘 / 账号管理 / 素材 / 代理 / 矩阵发布 / 任务 / 数据 / Agent / 工具 / 设置 …) | 1280×720 · 24fps · 32s |
| `prism_hyperframes_demo.gif` | 同上,循环 GIF | 720×405 · 256 帧 · 循环 |
| `prism_wrap.mp4` | 真实交互 walkthrough(登录弹窗 / Agent 对话),暗黑科技包装(标题卡 + 页面字幕 + 段间转场),基于新 UI 录屏 | 1280×720 · 24fps · 59.4s |
| `prism_wrap.gif` | 同上,循环 GIF | 720×405 · 475 帧 · 循环 |

- 均由 HyperFrames 确定性合成(SMPTE 帧级寻址,`window.__timelines["master"]` 驱动)。
- 统一 **暗黑科技** 风格(纯黑底 + 青色 `#22d3ee`/`#67e8f9` 高光 + 细网格 + 冷灰文字),对应新 UI 的纯黑单色界面并叠加青色科技高光。
- 账号管理场景使用「账户页实拍」图片(含 7 平台账号),作为宣传展示,未做脱敏。
- walkthrough 为真实交互录屏:账号登录弹窗(添加账号 → 选抖音 → 扫码)+ Hermes Agent 终端实时对话。

## 生成与再生成
源合成与脚本在 `output/hf-prism/`:
- `prism-demo/gen_composition.py` -> 14 页图片巡览合成(`prism_demo`),截图为 `output/shots/*.png`。
- `prism-wrap/index.html` -> 真实交互 walkthrough 叠加标题/字幕/转场(`prism_wrap`),底图为 `output/prism_walkthrough.mp4`。
- `output/walkthrough/capture_walkthrough_new.py` -> 重录新 UI 交互录屏(`output/prism_walkthrough.mp4`)。

再生成示例:
```bash
bash output/hf-prism/render_demo_v3.sh     # 重渲 prism_demo(暗黑科技, 无模糊/无去饱和)
bash output/hf-prism/render_final_wrap.sh  # 重渲 prism_wrap
```

> 注意:仓库 `.gitignore` 忽略 `*.mp4`,故本目录的 MP4 需用 `git add -f` 强制跟踪;GIF 可正常跟踪。
