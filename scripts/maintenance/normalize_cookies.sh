#!/bin/bash
# Cookie 文件规范化脚本
# 将所有账号文件重命名为清晰的格式

COOKIE_DIR="E:/SynapseAutomation/syn_backend/cookiesFile"
BACKUP_DIR="$COOKIE_DIR/backups/$(date +%Y%m%d_%H%M%S)_rename"

echo "=========================================="
echo "Cookie 文件规范化"
echo "=========================================="

# 创建备份目录
mkdir -p "$BACKUP_DIR"
echo "📁 备份目录: $BACKUP_DIR"
echo ""

cd "$COOKIE_DIR" || exit

# 备份所有现有文件
echo "1️⃣ 备份现有文件..."
cp *.json "$BACKUP_DIR/" 2>/dev/null
echo "✅ 备份完成"
echo ""

# 分析和显示重命名建议
echo "2️⃣ 分析现有文件，提供重命名建议..."
echo "=========================================="
echo ""

echo "📊 当前文件列表："
echo "----------------------------------------"
ls -1 *.json 2>/dev/null | grep -v "^douyin_\|^kuaishou_\|^bilibili_\|^xiaohongshu_" | while read file; do
    echo "  ❓ $file  ← 需要重命名"
done
echo ""

echo "📊 已规范化的文件："
echo "----------------------------------------"
ls -1 *.json 2>/dev/null | grep "^douyin_\|^kuaishou_\|^bilibili_\|^xiaohongshu_" | while read file; do
    echo "  ✅ $file"
done
echo ""

echo "=========================================="
echo "💡 重命名建议："
echo "=========================================="
echo ""
echo "手动重命名示例："
echo "  account_1765448130315.json  →  douyin_测试账号1.json"
echo "  account_1765453424195.json  →  kuaishou_主力号.json"
echo "  account_1765888429838.json  →  bilibili_账号1.json"
echo ""
echo "命名规范："
echo "  {平台}_{账号描述}.json"
echo ""
echo "  平台: douyin, kuaishou, bilibili, xiaohongshu"
echo "  描述: 测试账号, 主力号, 矩阵1号, 等等"
echo ""

# 可选：自动重命名（需要用户确认每个文件的平台）
echo "=========================================="
echo "🔧 自动重命名工具"
echo "=========================================="
echo ""
echo "⚠️  请手动检查 $COOKIE_DIR 中的文件"
echo "⚠️  根据账号用途重命名为规范格式"
echo ""
echo "示例："
echo "  cd $COOKIE_DIR"
echo "  mv account_1765448130315.json douyin_测试账号1.json"
echo "  mv account_1765453424195.json kuaishou_主力号.json"
echo ""
echo "✅ 备份已保存在: $BACKUP_DIR"
echo ""
