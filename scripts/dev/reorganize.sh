#!/bin/bash
# 项目结构重组脚本
# 使用方法: bash reorganize.sh

set -e  # 遇到错误立即退出

echo "======================================"
echo "  Prism 项目结构重组"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 确认操作
read -p "是否要开始重组项目结构？这将移动多个文件。(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "操作已取消"
    exit 1
fi

echo ""
echo "${YELLOW}开始重组...${NC}"
echo ""

# 1. 创建目录结构
echo "📁 创建目录结构..."
mkdir -p docs/archives
mkdir -p scripts/test
mkdir -p scripts/dev
mkdir -p scripts/deploy
mkdir -p temp
mkdir -p prism_backend/config
mkdir -p prism_backend/logs

# 2. 移动配置文件到后端
echo ""
echo "⚙️  移动配置文件..."
[ -f conf.py ] && mv -v conf.py prism_backend/config/ && echo "${GREEN}✓${NC} conf.py"
[ -f conf.example.py ] && mv -v conf.example.py prism_backend/config/ && echo "${GREEN}✓${NC} conf.example.py"
[ -f requirements.txt ] && mv -v requirements.txt prism_backend/ && echo "${GREEN}✓${NC} requirements.txt"

# 3. 移动后端脚本
echo ""
echo "🔧 移动后端脚本..."
[ -f migrate_db.py ] && mv -v migrate_db.py prism_backend/scripts/ && echo "${GREEN}✓${NC} migrate_db.py"

# 4. 移动日志文件
echo ""
echo "📝 移动日志文件..."
[ -f backend.log ] && mv -v backend.log prism_backend/logs/ && echo "${GREEN}✓${NC} backend.log"

# 5. 移动项目文档
echo ""
echo "📚 移动项目文档..."
[ -f README.md ] && mv -v README.md docs/ && echo "${GREEN}✓${NC} README.md"
[ -f SYSTEM_FEATURES.md ] && mv -v SYSTEM_FEATURES.md docs/ && echo "${GREEN}✓${NC} SYSTEM_FEATURES.md"
[ -f DEPENDENCIES.md ] && mv -v DEPENDENCIES.md docs/ && echo "${GREEN}✓${NC} DEPENDENCIES.md"

# 6. 归档旧文档
echo ""
echo "📦 归档旧文档..."
mv -v 填写范本提供*.pdf docs/archives/ 2>/dev/null && echo "${GREEN}✓${NC} PDF文档" || true
mv -v 填写范本提供*.docx docs/archives/ 2>/dev/null && echo "${GREEN}✓${NC} DOCX文档" || true

# 7. 移动测试脚本
echo ""
echo "🧪 移动测试脚本..."
[ -f test_all_apis.py ] && mv -v test_all_apis.py scripts/test/ && echo "${GREEN}✓${NC} test_all_apis.py"
[ -f test_api.py ] && mv -v test_api.py scripts/test/ && echo "${GREEN}✓${NC} test_api.py"
[ -f test_dashscope_response.py ] && mv -v test_dashscope_response.py scripts/test/ && echo "${GREEN}✓${NC} test_dashscope_response.py"

# 8. 移动开发脚本
echo ""
echo "🛠️  移动开发脚本..."
[ -f check_scripts.py ] && mv -v check_scripts.py scripts/dev/ && echo "${GREEN}✓${NC} check_scripts.py"
[ -f read_docs.py ] && mv -v read_docs.py scripts/dev/ && echo "${GREEN}✓${NC} read_docs.py"
[ -f cli_main.py ] && mv -v cli_main.py scripts/dev/ && echo "${GREEN}✓${NC} cli_main.py"

# 9. 移动部署脚本
echo ""
echo "🚀 移动部署脚本..."
[ -f setup-nginx.sh ] && mv -v setup-nginx.sh scripts/deploy/ && echo "${GREEN}✓${NC} setup-nginx.sh"
[ -f nginx.conf ] && mv -v nginx.conf scripts/deploy/ && echo "${GREEN}✓${NC} nginx.conf"

# 10. 移动临时文件
echo ""
echo "🗑️  移动临时文件..."
[ -f debug_ks_login.png ] && mv -v debug_ks_login.png temp/ && echo "${GREEN}✓${NC} debug_ks_login.png"

# 11. 创建新的README
echo ""
echo "📄 创建根目录README..."
cat > README.md << 'EOF'
# Prism

多平台内容分发自动化系统

## 📁 项目结构

```
Prism/
├── prism_backend/          # 后端服务（需同步到云）
├── prism_frontend/   # 前端服务（需同步到云）
├── docs/                 # 项目文档
├── scripts/              # 开发/测试/部署脚本
└── temp/                 # 临时文件
```

## 🚀 快速开始

### 后端
```bash
cd prism_backend
pip install -r requirements.txt
python app.py
```

### 前端
```bash
cd prism_frontend
npm install
npm run dev
```

## 📚 文档

详细文档请查看 `docs/` 目录：
- [系统功能](docs/SYSTEM_FEATURES.md)
- [依赖说明](docs/DEPENDENCIES.md)
- [部署指南](docs/DEPLOYMENT.md)

## 🔧 开发

测试和开发脚本位于 `scripts/` 目录。

## 📦 部署

部署脚本和配置位于 `scripts/deploy/` 目录。

---

**版本**: v2.0  
**更新日期**: 2025-11-26
EOF

echo "${GREEN}✓${NC} README.md 已创建"

# 12. 更新.gitignore
echo ""
echo "🔒 更新.gitignore..."
cat > .gitignore << 'EOF'
# 临时文件
temp/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# 后端
prism_backend/logs/*.log
prism_backend/data.db
prism_backend/cookiesFile/*.json
prism_backend/cookiesFile/backups/
prism_backend/config/conf.py

# 前端
prism_frontend/node_modules/
prism_frontend/.next/
prism_frontend/out/
prism_frontend/.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# 其他
*.log
.env
EOF

echo "${GREEN}✓${NC} .gitignore 已更新"

echo ""
echo "======================================"
echo "${GREEN}✅ 重组完成！${NC}"
echo "======================================"
echo ""
echo "📋 下一步："
echo "1. 检查文件是否正确移动"
echo "2. 测试后端: cd prism_backend && python app.py"
echo "3. 测试前端: cd prism_frontend && npm run dev"
echo "4. 查看新的项目结构: tree -L 2"
echo ""
