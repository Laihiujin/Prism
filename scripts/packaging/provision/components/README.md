# provision/components —— 隔离组件环境

本目录放**隔离型**组件的 micromamba `environment.yml`（每个组件一个子目录）。
「隔离型」指：需要**不同 Python 版本**或**冲突原生依赖**，不能和共享 `prismenv`
共享环境时才用。共享环境里能装下的组件走 `components.json` 的 `inject`（装进
`prismenv`，生成 `bin/<ep>` 入口），不需要这里的 yaml。

每个 `<name>/env.yaml` 使用 micromamba 语法：

```yaml
name: prism-<name>
channels:
{{CHANNELS}}          # 会被 provision.py 替换成所选镜像的 conda 通道列表
dependencies:
  - python=3.11
  - pip
  - # 原生包，例如 torch、特定 numpy 等
  - pip:
      - -r /abs/path/to/<name>/requirements.txt   # 该组件自己的 pip 依赖
```

## 用法

```bash
python3 scripts/packaging/provision/provision.py --component persona --mirror tuna
```

供给产物落在 `prism_components/<name>/`，并写出 `prism_components/<name>/prism-runtime.json`
（含该环境 python 路径）。`components.json` 的 `isolated` 数组登记后，`--all` 会逐个构建。

## 示例

- `persona/env.yaml` — persona-studio 隔离环境骨架。
