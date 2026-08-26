# AI 模块

这个目录包含了 Prism 项目的 AI 助手功能。

## 📁 目录结构

```
src/ai/
├── components/          # AI 相关的 React 组件
│   └── AiSidebar.tsx   # AI 聊天侧边栏组件
├── lib/                 # AI 核心逻辑
│   └── tools.ts        # AI 工具定义（脚本执行、状态检查等）
└── index.ts            # 模块导出
```

## 🔧 功能

### AiSidebar 组件
- 右侧可展开/收缩的聊天界面
- 实时流式响应
- 工具调用可视化
- 支持深色主题

### AI 工具 (tools.ts)
1. **execute_script** - 执行项目脚本
2. **check_status** - 检查后端服务状态
3. **read_logs** - 读取部署日志
4. **list_backend_scripts** - 列出后端可用脚本
5. **run_backend_script** - 运行后端脚本

## 📝 使用方式

### 导入组件
```tsx
import { AiSidebar } from "@/ai"
// 或
import { AiSidebar } from "@/ai/components/AiSidebar"
```

### 导入工具
```typescript
import { tools } from "@/ai"
// 或
import { tools } from "@/ai/lib/tools"
```

## 🔑 环境变量

需要在 `.env.local` 中配置：
```
OPENAI_API_KEY=your_api_key_here
```

## 🚀 API 路由

AI 聊天 API 位于: `src/app/api/chat/route.ts`

该路由使用本模块中定义的工具来处理用户请求。
