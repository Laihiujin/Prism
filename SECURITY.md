# 安全策略 / Security Policy

## 支持范围 / Supported Versions

本项目以自托管方式分发，维护跟随默认分支 `main` 的最新代码：

| Version | Supported |
|---|---|
| `main`（最新） | ✅ |
| 历史 tag / 旧分支 | ❌ 仅接受补丁，不做主动维护 |

## 报告漏洞 / Reporting a Vulnerability

**请勿在公开 Issue、Discussion 或 PR 中披露漏洞细节。**

请通过 GitHub 私有渠道提交：

- **[Security Advisory](https://github.com/Laihiujin/Prism/security/advisories/new)**（推荐，可附私有复现说明与补丁草案）

或联系仓库维护者（GitHub @Laihiujin）。

我们会：

1. 在 72 小时内确认收到报告；
2. 评估影响范围与严重性，通常在一周内给出修复计划；
3. 修复合并后按需发布安全公告（GitHub Security Advisory）。

## 报告内容建议

- 影响组件与版本（commit）
- 复现步骤 / PoC（脱敏：不要包含 Cookie、登录态、代理凭证、API Key）
- 期望行为与实际行为
- 如能提供修复建议更好

## 安全范围与已知注意事项

本项目是**自动化对接第三方平台的自托管系统**，以下事项请自行评估并做好防护：

- **CORS 默认 `allow_origins=["*"]`**（`prism_backend/fastapi_app/main.py`）——对外暴露 API 前必须收紧；
- 爬虫登录态配置（如含 cookie/ttwid 的 `config.yaml`）包含真实凭证，**不入库**，请保护本机文件权限并避免进入任何备份/上传目录；
- 浏览器身份（fingerprint / profile / 代理绑定）即账号凭据的一部分，泄露等同账号泄露；
- 本项目**不提供任何形式的漏洞赏金（bug bounty）**；
- 使用本项目规模化运营前，请遵守各平台服务条款并建立内部审核机制（见 README「合规提示」）。
