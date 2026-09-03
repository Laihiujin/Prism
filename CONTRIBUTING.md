# 给想帮忙的你 / Contributing

这个项目目前基本就我一个人在维护。所以如果你真的愿意花时间提个 PR、报个 bug、甚至只是看两眼，我都特别感激——真的，不是客套。

我不觉得自己写得多好，项目里也一堆我自己知道的问题。所以你来都不用有压力：

- **补测试**：README 里我自己都承认测试薄，你能补上任何一块我都很谢谢。
- **加平台适配器**：`prism_backend/platforms/` 里照着一个现成的改就行，结构都差不多。
- **修 bug**：发视频失败、登录抽风那种，我自己的坑，你愿意趟我特别欢迎。
- **挑文档毛病**：错别字、翻译不对、吹牛吹过头的地方，尽管说，我改。
- **不想写代码**：那点个 star 我就很开心了。

## 跑起来

```bash
python -m venv prismenv && source prismenv/bin/activate
pip install -r requirements.txt

cd prism_frontend && npm install && cd ..

cp env.example .env        # 按需改
./start-pm2.sh             # macOS；Windows 用 start.bat
```

万一跑不起来，直接发 issue 问就行，不用一个人跟报错死磕。

## 提 issue / PR

- 报 bug 带上环境和复现步骤。**日志先脱敏**——cookie / 登录态 / 代理凭证发出来，等于账号直接裸奔，我救不回来。
- 一个 PR 一件事就好，一个 PR 塞十件事我可能会看晕。
- 提交信息随大流：`fix(xxx): ...` / `feat(xxx): ...`，中英文都行。
- 提交前自己过一遍，前端别让 `npm run build` 出红，发布先用测试账号。
- 我改自己的代码都靠 git 保命，所以你的 PR 顶多让你 rebase 一下，别怕。

## 唯一注意的

Cookie、浏览器 profile、指纹、代理数据、API key——**别提交**。`.gitignore` 基本都挡了，别 `git add -f` 硬塞。这些东西一旦进了历史，想删干净特别费劲。

## 风格

大概齐就行，我自己也没多规范。动了 API / CLI / 目录结构，顺手同步 `docs/hermes-skills/prism-project-layout/SKILL.md`，忘了也没关系，我会小声提醒你。

行为守则见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)——就一句话：互相尊重，别闹。

感谢每一位愿意花时间帮这个项目的人 🙏
