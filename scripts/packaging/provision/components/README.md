# provision/components —— 隔离组件环境

本目录放**隔离型**组件的 micromamba `environment.yml`（每个组件一个子目录）。
「隔离型」指：**独立进程、独立入口**的组件（persona / hermes / 未来的 MCP、插件），
需要自己的 Python 运行时和依赖，不能和共享 `prismenv` 混在一起（否则会互相抢版本）。

共享 `prismenv` 只留 Prism 本体 + **被后端进程直接 import 的库**（`biliup`、
`douyin_tiktok_api`）。这两类是靠 `requirements.prism.lock.txt` 锁版本，不走隔离。

## 每个 `<name>/env.yaml` 只写 conda 层

组件本体（`pip install -e`，含 extras）由 provision.py 依据 `components.json` 的
`isolated` 元数据安装并生成 `bin/<name>` 入口。所以 env.yaml 只需 `python` + `pip`：

```yaml
name: prism-<name>
channels:
{{CHANNELS}}          # 会被 provision.py 替换成所选镜像的 conda 通道列表
dependencies:
  - python=3.11
  - pip
```

## 在 `components.json` 登记组件元数据

```json
{
  "name": "<name>",
  "src": "tools/<name>",
  "pip": "tools/<name>",
  "extras": ["api", "launch"],
  "entrypoints": ["<name>"]
}
```

- `pip`：组件本体目录（缺省用 `src`）；`extras`：安装时附加的 PEP 508 extras。

## 用法

```bash
# 构建单个隔离组件环境
python3 scripts/packaging/provision/provision.py --component persona --mirror tuna

# 卸载隔离组件 = 删除 prism_components/<name> 环境，释放空间给下一个组件
python3 scripts/packaging/provision/provision.py --uninstall persona

# 卸载 node 组件（deepseek-harness）= 删除整个 tools/<name>
#   带运行中保护：组件声明了 port 且仍在监听 → 拒绝；
#   源码保护：嵌套 repo 有未提交修改 → 拒绝，除非加 --force
python3 scripts/packaging/provision/provision.py --uninstall deepseek-harness

# 只清 node 组件依赖（node_modules，保留源码），用于依赖损坏后重装
python3 scripts/packaging/provision/provision.py --reset-deps deepseek-harness

# 一键构建所有隔离组件（含共享 prismenv + 系统依赖 stage）
python3 scripts/packaging/provision/provision.py --all --mirror tuna
```

供给产物落在 `prism_components/<name>/`，并写出 `prism-runtime.json`（含该环境
python 路径 + `component: <name>`）。ecosystem 用 `compPyCliArgs('<name>', '<name>', ...)`
指向该组件的 `bin/<name>` 启动。

## 示例

- `persona/env.yaml` — persona-studio 隔离环境（engine，extras `api,launch,secure`）。
- `hermes/env.yaml` — hermes-agent 隔离环境。
