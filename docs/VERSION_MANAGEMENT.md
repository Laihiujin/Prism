# 版本号管理说明

## 使用方法

### 方式 1: 命令行参数指定版本号
```batch
build-package.bat 2.3.0
```
直接在命令行传入版本号，脚本会使用该版本号进行构建。

### 方式 2: 自动递增模式
```batch
set SYNAPSE_AUTO_YES=1
build-package.bat
```
在自动模式下，脚本会自动递增 patch 版本号（例如：2.2.0 → 2.2.1）。

### 方式 3: 交互式选择
```batch
build-package.bat
```
不带参数运行时，脚本会显示版本选择菜单：
```
Version options:
  [1] Keep current version: 2.2.0
  [2] Auto increment patch: 2.2.1
  [3] Enter custom version
```

## 版本号格式

版本号必须遵循 **语义化版本规范** (Semantic Versioning)：
- 格式：`MAJOR.MINOR.PATCH`
- 示例：`2.3.0`, `1.0.5`, `3.2.1`

## 版本号存储

版本号会保存在两个位置：
1. **`desktop-electron/package.json`** - Electron 应用的版本号
2. **`desktop-electron/build-version.json`** - 构建历史记录

## 构建号 (Build Number)

每次构建都会自动递增构建号，格式为 `v{number}`：
- 第一次构建：v1
- 第二次构建：v2
- 以此类推...

输出目录会使用构建号命名：`dist-out/v{BUILD_NUM}/`

## 示例

### 发布新的 minor 版本
```batch
build-package.bat 2.3.0
```

### 发布 patch 更新
```batch
build-package.bat 2.2.1
```

### 快速构建（自动递增）
```batch
set SYNAPSE_AUTO_YES=1
set SYNAPSE_PACKAGE_TYPE=2
build-package.bat
```

## 注意事项

1. 版本号会在构建开始前更新到 `package.json`
2. 构建完成后，版本号和构建号会保存到 `build-version.json`
3. 如果输入的版本号格式不正确，脚本会报错并退出
4. 建议按照语义化版本规范管理版本号：
   - MAJOR：不兼容的 API 修改
   - MINOR：向下兼容的功能性新增
   - PATCH：向下兼容的问题修正
