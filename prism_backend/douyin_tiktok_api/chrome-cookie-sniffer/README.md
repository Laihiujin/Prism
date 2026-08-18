# Chrome Cookie Sniffer

一个用于自动嗅探和提取网站Cookie的Chrome扩展程序。支持抖音等主流平台，具备智能去重、时间控制和Webhook回调等功能。

## 功能特性

- 🎯 **智能Cookie抓取** - 自动拦截POST/GET请求中的Cookie
- ⏱️ **防重复机制** - 5分钟内不重复抓取相同服务
- 🔄 **内容去重** - 只有Cookie内容变化时才保存
- 🎨 **现代化界面** - Card列表展示，状态一目了然
- 🔗 **Webhook回调** - Cookie更新时自动推送到指定地址
- 📋 **一键复制** - 快速复制Cookie到剪贴板
- 🗂️ **数据管理** - 支持导出、清理和单独删除
- 🔧 **调试友好** - 内置Webhook测试功能

## 支持的网站

- 🎵 **抖音** (douyin.com)
- 🚀 **扩展性** - 架构支持轻松添加更多平台

## 安装方法

### 1. 下载源码

```bash
git clone <repository-url>
# 或直接下载ZIP文件并解压
```

### 2. 在Chrome中加载扩展

1. **打开Chrome扩展管理页面**
   - 方法一：地址栏输入 `chrome://extensions/`
   - 方法二：菜单 → 更多工具 → 扩展程序

2. **启用开发者模式**
   - 在扩展管理页面右上角，开启"开发者模式"开关

3. **加载解压的扩展程序**
   - 点击"加载已解压的扩展程序"按钮
   - 选择 `chrome-cookie-sniffer` 文件夹
   - 确认加载

4. **验证安装**
   - 扩展列表中出现"Cookie Sniffer"
   - 浏览器工具栏出现扩展图标
   - 状态显示为"已启用"

### 3. 权限确认

安装时Chrome会请求以下权限：
- `webRequest` - 拦截网络请求
- `storage` - 本地数据存储  
- `cookies` - 读取Cookie信息
- `activeTab` - 当前标签页访问
- `host_permissions` - 访问douyin.com域名

## 使用方法

### 基础使用

1. **访问目标网站** - 打开抖音等支持的网站
2. **触发请求** - 正常浏览，触发POST/GET请求
3. **查看结果** - 点击扩展图标查看抓取的Cookie

### 配置Webhook

1. **打开扩展弹窗**
2. **输入Webhook地址** - 在顶部输入框填入回调URL
3. **测试连接** - 点击"🔧 测试"按钮验证
4. **自动回调** - Cookie更新时自动POST到指定地址

### Webhook数据格式

```json
{
  "service": "douyin",
  "cookie": "具体的Cookie字符串",
  "timestamp": "2025-08-29T12:34:56.789Z"
}
```

测试时会额外包含：
```json
{
  "test": true,
  "message": "这是一个测试回调..."
}
```

### 数据管理

- **📋 复制Cookie** - 点击卡片中的复制按钮
- **🗑️ 删除数据** - 删除单个服务的Cookie
- **🔄 刷新** - 手动刷新数据显示
- **📤 导出** - 导出所有数据为JSON文件
- **🧹 清空** - 清空所有Cookie数据

## 调试指南

### 查看日志

1. **打开扩展管理页面** (`chrome://extensions/`)
2. **找到Cookie Sniffer扩展**
3. **点击"服务工作进程"** - 查看蓝色链接
4. **查看控制台输出** - 所有日志都在这里

### 常见问题

**Q: 扩展不工作？**
- 检查是否启用开发者模式
- 确认权限已正确授予
- 查看service worker是否正在运行

**Q: 没有抓取到Cookie？**
- 确认访问的是支持的网站
- 检查是否触发了POST/GET请求
- 查看service worker控制台日志

**Q: Webhook测试失败？**
- 检查URL格式是否正确
- 确认服务器支持跨域请求
- 验证服务器是否正常响应

### 开发者选项

修改 `background.js` 中的 `SERVICES` 配置来添加新网站：

```javascript
const SERVICES = {
  douyin: {
    name: 'douyin',
    displayName: '抖音',
    domains: ['douyin.com'],
    cookieDomain: '.douyin.com'
  },
  // 添加新服务
  bilibili: {
    name: 'bilibili',
    displayName: 'B站',
    domains: ['bilibili.com'],
    cookieDomain: '.bilibili.com'
  }
};
```

## 文件结构

```
chrome-cookie-sniffer/
├── manifest.json          # 扩展配置文件
├── background.js          # 后台服务脚本
├── popup.html            # 弹窗界面
├── popup.js              # 弹窗逻辑
└── README.md             # 说明文档
```

## 注意事项

- ⚠️ **仅用于合法用途** - 请遵守网站服务条款
- 🔒 **数据安全** - Cookie数据存储在本地，不会上传
- 🔄 **定期更新** - 网站更新可能影响抓取效果
- 📱 **Chrome限制** - 部分网站可能有反爬虫机制

## 开源协议

本项目遵循 MIT 开源协议。

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！