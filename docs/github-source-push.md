# GitHub 源码推送边界

## 目标

只推源码、配置模板和必要文档；不推运行时数据、账号数据、日志、打包产物和本地资源缓存。

## 已收紧的内容

- 顶层 `dist/`、`dist-out/`、`build/supervisor/` 已忽略。
- `desktop-electron/dist-build/`、`desktop-electron/dist-out/`、`desktop-electron/resources/`、`desktop-electron/syn_backend/` 已忽略。
- 运行时账号数据、cookies、指纹、浏览器配置、数据库、日志仍保持忽略。
- Electron 安装包构建不再携带顶层 `.env`。

## 推荐推送范围

- `syn_backend/`
- `syn_frontend_react/`
- `desktop-electron/src/`
- `scripts/`
- `config/` 中的模板和静态配置
- `.github/workflows/`
- `docs/`

## 推送前检查

1. 确认 `git status` 中没有 `dist`、`dist-out`、`resources`、数据库、日志文件。
2. 确认未提交 `.env`、cookies、账号快照、浏览器 profile。
3. 如需发版，先执行 `scripts/packaging/build-package.bat`，它会自动清空日志和账号类数据目录再打包。
