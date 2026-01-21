欢迎安装 SynapseAutomation
===========================================

## 新功能

### 1. 视频数据管理
- ✨ 新增一键清除视频数据功能
- 📦 支持自动备份视频文件和分析数据
- 🗑️ 可清除所有视频文件、video_analytics 和 analytics_history 数据

### 2. 系统设置增强
- 🎛️ 完善的数据清理工具
- 💾 智能备份机制
- 🔄 改进的服务重启功能

### 3. 前后端联调优化
- 🌐 支持浏览器和 Electron 双模式
- 🚀 优化的 API 性能
- 🔧 更好的错误处理

## 系统要求

- Windows 10/11 (64-bit)
- 至少 8GB RAM
- 至少 5GB 可用磁盘空间
- Python 3.10+ (内置)
- Node.js 环境 (内置)

## 安装说明

1. 选择安装目录
2. 等待文件复制完成
3. 首次启动会自动初始化数据库
4. 默认端口:
   - 前端: http://localhost:3000
   - 后端: http://localhost:7000

## 使用指南

### 首次使用
1. 启动应用后等待服务初始化
2. 访问系统设置页面检查服务状态
3. 添加平台账号开始使用

### 清除视频数据
1. 打开系统设置页面
2. 找到"数据清理"区域
3. 点击"清除视频数据"
4. 确认操作（建议保持"自动备份"选中）

## 技术支持

如遇问题请查看日志文件：
- 应用日志: %APPDATA%\SynapseAutomation\logs
- 后端日志: 安装目录\syn_backend\logs

## 数据备份

重要数据备份位置：
- 视频数据: 安装目录\syn_backend\backups\video_data_*
- 数据库: 安装目录\syn_backend\db\
- Cookie: 安装目录\syn_backend\cookiesFile\

===========================================
© 2026 Synapse Team. All rights reserved.
