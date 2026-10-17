---
name: prism-product-lock
description: 产品锁定。凡是生图或改图里出现真实产品——产品图、带产品的场景图、人物与产品的交互图——每次都先附产品原图并带固定的产品描述；场景和人物写成可替换的槽位，用脚本从第一镜到最后一镜整套替换，产品外观不变、不用反复抽卡。用于封面、海报、分镜静帧和多场景/多人物改版。
---

# 产品锁定

图像模型知道产品“长什么样”，但每次重新生成都会把它画得不一样。这个技能把产品当成整套画面里唯一不能动的东西：原图永远排在参考图最前面，产品描述是一段固定文字，场景和人物才是可以换的部分。

## 什么时候必须用

- **产品图**：packshot、hero 特写、电商主图。
- **产品在场景里**：门上的锁、桌上的机器、货架上的包装，哪怕只在背景里。
- **人与产品互动**：开锁、握持、佩戴、操作。

纯场景、纯人物、产品不出镜的画面不需要原图，但仍按同一份镜头计划管理。

## 六条规则

1. **原图先行。** 参考图顺序固定为：产品原图（按画面里能看到的那一面挑）→ 场景图 → 人物 → 构图参考。
2. **每次重新附上。** 每次生成、每次修改都重新上传原图。不依赖对话记忆、缓存、上一张输出或 prompt 里的型号名。
3. **产品描述是固定文字。** `memory` 和每个单元的 `keep` 清单原样放在 prompt 开头，换场景、换人时一个字都不改。
4. **只有原图能决定产品外观。** 生成图只能当构图或场景参考；上一版输出做连续性时必须和原图一起出现。失败的图永远不会变成新的产品依据。
5. **场景和人物是槽位。** 镜头只写 `location` / `plate` / `roles`，具体用哪个场景、哪个人由 `bindings` 决定。
6. **物理逻辑优先。** 产品怎么装、哪些面不能同框（例如门内外两块面板），先写产品逻辑卡（`product-logic.example.json` 的结构），不可能的镜头在生成前拒绝。

## 两份文件

- 产品锁定卡：`references/product-lock.example.json`，结构见 `references/product-lock.schema.json`。`originals` 每张原图写清路径、视角、`provenance: "original"`、负责哪个单元；`identity` 写每个单元必须保留的外观；`drift_traps` 写这个产品被画错过的样子（只进验收，不进 prompt）。
- 镜头计划：`references/shot-plan.example.json`，结构见 `references/product-shot-plan.schema.json`。场景按侧给 plate（门外 / 门内 / 远景），没生成的标 `status: "to_generate"`；人物写 `carry`（哪只手拿着什么）和可选的 `release`（怎么腾出一只手）。

## 编译与整套替换

```bash
python scripts/compile_product_lock.py references/shot-plan.example.json
python scripts/compile_product_lock.py plan.json --bind home=SCENE-B --bind lead=CHAR-C
python scripts/compile_product_lock.py plan.json --matrix home=SCENE-B,SCENE-C --matrix lead=CHAR-C,CHAR-D --out 替换矩阵.md
```

输出每一镜的参考图上传顺序、完整 prompt、验收清单和产品段摘要。矩阵模式会比对所有组合的产品段，任何一镜漂移就返回非零。脚本还会自动处理这些情况：

- 场景缺图：列为“先补场景图”，提示带原图生成。
- 门外镜头配了门内场景图：标 BLOCKER。
- 互动镜头那只手拿着东西：有空手就换成空手；两只手都占着时，人物有 `release` 就按它腾手，没有就标 BLOCKER。

## 在 Prism 里执行

- 生成封面或静帧时，按编译结果的顺序把原图、场景图和人物图一起传给支持参考图的接口（`generate_cover` 只接受一张参考图时，先用宿主的多图工具生成，再导入素材选用）。工具不支持参考图时，换一个支持的工具，不要退回纯文生图。
- 本地记录每次调用实际上传的原图路径与 SHA-256。
- 看实际生成的图：产品区域与原图并排比对，`identity` 逐条打勾，`drift_traps` 一条都不出现。

品牌专属的原图、产品逻辑卡和样稿只放私有环境，不进入本仓库。`scripts/compile_product_lock.py` 与 CineForge-Skills 中的同名脚本保持一致。
