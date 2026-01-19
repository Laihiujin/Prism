# SynapseAutomation 打包系统使用指南

## 📦 打包脚本说明

### build-package.bat - 智能打包系统

这是一个全自动的打包脚本，具有以下特性：

#### ✨ 主要功能

1. **自动检测并停止运行中的进程**
   - 自动检测 SynapseAutomation.exe 和 supervisor.exe
   - 避免"文件被占用"错误

2. **Supervisor 状态检查**
   - 验证 supervisor.exe 是否已编译
   - 确保后端服务管理器就绪

3. **智能版本管理**
   - 自动读取和更新版本号
   - 版本号格式：1.0.0 → 1.0.1 → 1.0.2
   - 构建编号：v1 → v2 → v3

4. **多种打包方式**
   - **NSIS**: electron-builder 默认方式
   - **Inno Setup**: 推荐，支持中文界面
   - **仅目录**: 快速测试，不生成安装程序

5. **分阶段打包流程**
   - **阶段1**: 先打包 win-unpacked 目录
   - **测试阶段**: 用户测试 exe 和服务
   - **阶段2**: 确认后打包 setup.exe

6. **版本化输出**
   - 输出到 `desktop-electron/dist-out/v{buildNumber}/`
   - 每次打包创建新版本目录
   - 便于版本对比和回滚

#### 📋 使用步骤

```batch
# 1. 运行打包脚本
build-package.bat

# 2. 按提示操作：
#    - 如有进程运行，选择是否停止
#    - 选择打包方式 (1: NSIS / 2: Inno Setup / 3: 仅目录)
#    - 等待第一阶段完成

# 3. 测试 unpacked 版本：
desktop-electron\dist-out\v1\win-unpacked\SynapseAutomation.exe

# 4. 确认无误后，按 Y 继续打包安装程序

# 5. 完成！检查输出目录：
desktop-electron\dist-out\v1\
```

#### 📁 输出目录结构

```
desktop-electron/
├── dist-out/
│   ├── v1/
│   │   ├── win-unpacked/              # 可直接运行的目录
│   │   │   └── SynapseAutomation.exe
│   │   └── SynapseAutomation-Setup-v1.exe  # 安装程序
│   ├── v2/
│   │   ├── win-unpacked/
│   │   └── SynapseAutomation-Setup-v2.exe
│   └── ...
└── build-version.json                 # 版本追踪文件
```

#### ⚙️ 版本管理

版本信息存储在 `desktop-electron/build-version.json`:

```json
{
  "version": "1.0.0",
  "buildNumber": 1,
  "lastBuildDate": "2026-01-09"
}
```

- **version**: 语义化版本号（自动递增 PATCH 版本）
- **buildNumber**: 构建编号（每次打包 +1）
- **lastBuildDate**: 最后打包时间

#### 🔧 打包方式对比

| 方式 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| NSIS | electron-builder 内置，无需额外安装 | 中文支持较弱 | 快速打包 |
| Inno Setup | 中文界面好，自定义程度高 | 需要安装 Inno Setup | 正式发布 |
| 仅目录 | 最快，适合测试 | 无安装程序 | 开发测试 |

#### 📝 注意事项

1. **首次使用**
   - 确保已运行 `npm install`
   - 确保 supervisor.exe 已编译（运行 `build-supervisor.bat`）
   - Inno Setup 打包需要安装: https://jrsoftware.org/isdl.php

2. **编译 Supervisor**
   ```batch
   # 方法1: 使用便捷脚本（推荐）
   build-supervisor.bat

   # 方法2: 手动编译
   pyinstaller build\supervisor.spec --clean
   ```

   如果遇到版本兼容性问题：
   ```batch
   # 升级 PyInstaller 到最新版本
   pip install --upgrade pyinstaller
   ```

2. **打包前**
   - 关闭所有运行中的 SynapseAutomation 实例
   - 确保没有编辑器打开 dist 目录中的文件
   - 建议先运行 `clean-dist.bat` 清理旧文件

3. **测试阶段**
   - 务必测试 unpacked 版本的所有功能
   - 检查 supervisor 是否正常启动
   - 检查后端和前端是否正常工作
   - 确认无误后再打包安装程序

4. **版本号规则**
   - 每次打包自动递增 PATCH 版本（1.0.0 → 1.0.1）
   - 手动修改 build-version.json 可更改版本号
   - 构建编号（v1, v2...）始终递增，不可重置

#### 🐛 常见问题

**Q: 打包失败，提示"文件被占用"**
A: 脚本会自动检测并停止进程，如仍失败：
- 手动关闭所有相关进程
- 运行 `desktop-electron\clean-build.bat`
- 重新运行打包脚本

**Q: Supervisor 未找到**
A: 需要先编译 supervisor：
```batch
# 推荐方式 - 使用便捷脚本
build-supervisor.bat

# 或手动编译
pyinstaller build\supervisor.spec --clean
```

**Q: PyInstaller 报错 "unexpected keyword argument 'hooksconfig'"**
A: PyInstaller 版本过旧，解决方案：
```batch
# 方案1: 升级 PyInstaller（推荐）
pip install --upgrade pyinstaller

# 方案2: 使用已修复的 spec 文件
# supervisor.spec 已修复兼容性问题，直接运行即可
```

**Q: Inno Setup 打包失败**
A:
- 确保已安装 Inno Setup 6
- 检查路径：`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
- 或选择 NSIS 打包方式

**Q: 如何回滚到旧版本？**
A: dist-out 保留了所有历史版本：
```batch
# 直接运行旧版本
desktop-electron\dist-out\v1\win-unpacked\SynapseAutomation.exe

# 或使用旧的安装程序
desktop-electron\dist-out\v1\SynapseAutomation-Setup-v1.exe
```

#### 🚀 完整打包流程示例

```batch
# 1. 清理环境（可选）
cd desktop-electron
clean-build.bat
cd ..

# 2. 编译 supervisor
build-supervisor.bat

# 3. 运行打包
build-package.bat

# 输出示例：
# ============================================
#   SynapseAutomation 智能打包系统
# ============================================
#
# [1/6] 检查并停止正在运行的进程...
# ✅ 没有运行中的进程
#
# [2/6] 检查 Supervisor 状态...
# ✅ Supervisor 已就绪
# 路径: E:\...\build\supervisor\supervisor.exe
#
# [3/6] 读取版本信息...
# 当前版本: 1.0.0
# 构建编号: v1
#
# [4/6] 清理旧的构建文件...
# ✅ 清理完成
#
# [5/6] 选择打包方式
# 请选择 (1/2/3): 2
#
# [6/6] 开始打包...
# ⏱️  正在打包 win-unpacked 目录...
#
# ✅ 第一阶段完成！
# 📦 已生成目录: dist-out\v1\win-unpacked
#
# 是否继续打包安装程序 (Setup.exe) [Y/N]? y
#
# 使用 Inno Setup 打包...
# ✅ Inno Setup 安装程序已生成
#
# ============================================
# ✅ 打包完成！
# ============================================
```

## 🔗 相关文件

- [build-package.bat](build-package.bat) - 主打包脚本
- [build-supervisor.bat](build-supervisor.bat) - Supervisor 编译脚本
- [build/supervisor.spec](build/supervisor.spec) - Supervisor 编译配置
- [desktop-electron/build-version.json](desktop-electron/build-version.json) - 版本追踪
- [desktop-electron/installer.iss](desktop-electron/installer.iss) - Inno Setup 配置
- [desktop-electron/clean-build.bat](desktop-electron/clean-build.bat) - 清理脚本
- [desktop-electron/package.json](desktop-electron/package.json) - 项目配置

## 📞 技术支持

如遇问题，请检查：
1. 打包日志输出
2. electron-builder 错误信息
3. supervisor.exe 是否存在
4. Node.js 和 npm 版本

---
© 2026 Synapse Team. All rights reserved.
