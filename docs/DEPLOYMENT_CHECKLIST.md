# SynapseAutomation AI配置系统 - 部署清单

## ✅ 已完成的工作

### 1. 后端开发
- ✅ 创建统一配置文件 `syn_backend/config/ai_prompts_unified.yaml`
- ✅ 创建API模块 `syn_backend/fastapi_app/api/v1/ai_prompts/`
- ✅ 更新配置加载逻辑 `syn_backend/ai_service/ai_client.py`
- ✅ 更新Agent提示词 `syn_backend/fastapi_app/api/v1/agent/prompts.py`
- ✅ 注册API路由 `syn_backend/fastapi_app/api/v1/router.py`

### 2. 前端开发
- ✅ 创建配置管理页面 `syn_frontend_react/src/app/ai-agent/prompts/page.tsx`
- ✅ 更新API端点配置 `syn_frontend_react/src/lib/env.ts`
- ✅ 添加导航入口到设置页面

### 3. 工具和文档
- ✅ 创建一键打包脚本 `build-package.bat`
- ✅ 创建使用指南 `AI_PROMPTS_GUIDE.md`
- ✅ 创建API测试脚本 `test_ai_prompts_api.py`

---

## 📋 测试清单

### 后端测试

#### 1. 启动后端服务
```bash
cd syn_backend
python fastapi_app/run.py
```

预期输出：
```
[AIClient] Loaded prompts from E:\SynapseAutomation\syn_backend\config\ai_prompts_unified.yaml
[START] SynapseAutomation v1.x.x
[SERVER] http://localhost:7000
```

#### 2. 测试API接口
```bash
python test_ai_prompts_api.py
```

预期输出：所有测试通过 ✅

#### 3. 访问API文档
打开浏览器访问: http://localhost:7000/api/docs

查找 `/api/v1/ai-prompts` 相关接口，应包含：
- GET `/api/v1/ai-prompts/structure`
- GET `/api/v1/ai-prompts/config/{config_key}`
- PUT `/api/v1/ai-prompts/config/{config_key}`
- POST `/api/v1/ai-prompts/config/{config_key}/reset`
- GET `/api/v1/ai-prompts/metadata`

### 前端测试

#### 1. 启动前端服务
```bash
cd syn_frontend_react
npm install
npm run dev
```

#### 2. 访问配置页面
打开浏览器访问: http://localhost:3000/ai-agent/prompts

**测试步骤:**
1. ✅ 检查左侧导航是否显示所有分类
2. ✅ 点击不同的配置项，右侧应显示对应内容
3. ✅ 检查面包屑导航是否正确
4. ✅ 编辑提示词内容，应显示"有未保存的更改"
5. ✅ 点击"保存更改"，应显示成功提示
6. ✅ 点击"重置"，应弹出确认对话框
7. ✅ 检查只读配置是否显示"不可编辑"提示

#### 3. 测试导航
从设置页面 (http://localhost:3000/ai-agent/settings):
1. ✅ 检查页面右上角是否有"提示词配置"按钮
2. ✅ 点击按钮，应跳转到配置页面
3. ✅ 在配置页面点击"返回设置"，应跳转回设置页面

### AI功能验证

#### 1. 测试标题生成
```bash
curl -X POST http://localhost:7000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "给我起一个视频标题", "stream": false}'
```

#### 2. 测试聊天功能
访问: http://localhost:3000/ai-agent

发送消息，检查AI是否正确使用新配置的提示词

---

## 🔧 故障排查

### 问题 1: 后端启动失败
**症状:** `[AIClient] Config file not found`

**解决方案:**
1. 检查文件是否存在: `syn_backend/config/ai_prompts_unified.yaml`
2. 如果不存在，从备份恢复或使用旧配置

### 问题 2: API返回404
**症状:** 访问 `/api/v1/ai-prompts` 返回404

**解决方案:**
1. 检查 `syn_backend/fastapi_app/api/v1/router.py` 中是否导入了 `ai_prompts_router`
2. 检查是否正确注册了路由
3. 重启后端服务

### 问题 3: 前端页面空白
**症状:** 访问配置页面显示空白

**解决方案:**
1. 打开浏览器控制台查看错误
2. 检查 `syn_frontend_react/src/lib/env.ts` 中 `AI_PROMPTS` 端点配置
3. 检查后端API是否正常响应
4. 清除浏览器缓存并刷新

### 问题 4: 配置未生效
**症状:** 修改配置后AI行为未改变

**解决方案:**
1. 确认保存成功（前端应显示成功提示）
2. 检查备份文件 `ai_prompts_unified.yaml.bak` 是否生成
3. 重启后端服务以重新加载配置
4. 检查后端日志确认配置已加载

---

## 📦 打包部署

### 使用一键打包脚本

#### 自动版本号（推荐）
```bash
build-package.bat
```
自动检测最新版本并递增（如 v1 -> v2）

#### 指定版本号
```bash
build-package.bat v5
```
创建 `desktop-electron/dist-v5` 目录

### 打包输出
```
desktop-electron/
└── dist-v2/
    ├── win-unpacked/
    │   └── SynapseAutomation.exe
    ├── VERSION.txt
    └── README.txt
```

### 分发给用户
1. 将 `dist-v2` 文件夹压缩
2. 同时提供 `syn_backend` 文件夹
3. 提供使用说明

---

## 🗑️ 清理工作

### 确认无误后可删除

#### 旧配置文件
```bash
# 在 syn_backend/config/ 目录下
rm ai_prompts.yaml
rm ai_prompts_refactored.yaml
```

**⚠️ 删除前确认:**
1. ✅ 新配置文件 `ai_prompts_unified.yaml` 存在且正常工作
2. ✅ 所有AI功能测试通过
3. ✅ 已创建备份 `ai_prompts_unified.yaml.bak`

---

## 📊 验收标准

### 后端验收
- [x] 后端启动无错误
- [ ] API接口测试全部通过
- [ ] Swagger文档正确显示所有接口
- [ ] 配置文件正确加载
- [ ] AI功能使用新配置

### 前端验收
- [ ] 配置页面正常显示
- [ ] 所有配置项可正常访问
- [ ] 编辑功能正常工作
- [ ] 保存功能正常工作
- [ ] 重置功能正常工作
- [ ] 导航正确
- [ ] 面包屑显示正确

### 集成验收
- [ ] 前端修改配置后后端立即生效
- [ ] 重启服务后配置持久化
- [ ] 备份机制正常工作
- [ ] 只读配置无法修改
- [ ] 所有AI模块使用新配置

---

## 📞 下一步

1. **运行测试脚本**
   ```bash
   python test_ai_prompts_api.py
   ```

2. **手动测试前端**
   - 访问配置页面
   - 测试所有功能

3. **验证AI功能**
   - 测试标题生成
   - 测试文案生成
   - 测试聊天功能

4. **清理旧文件**
   - 确认无误后删除旧配置

5. **创建发布版本**
   ```bash
   build-package.bat
   ```

---

**完成日期:** 2026-01-07
**版本:** 3.0
**维护:** SynapseAutomation Team
