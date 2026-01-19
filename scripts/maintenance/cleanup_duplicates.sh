#!/bin/bash
# 清理重复和无用目录脚本

echo "=========================================="
echo "清理重复和无用目录"
echo "=========================================="

# 1. 删除带空格的 playwright 目录
echo "1️⃣ 删除重复的 .playwright-browsers 目录（带空格）..."
if [ -d "E:/SynapseAutomation/.playwright-browsers " ]; then
    rm -rf "E:/SynapseAutomation/.playwright-browsers "
    echo "✅ 已删除: .playwright-browsers （末尾空格）"
    echo "   释放空间: ~644MB"
else
    echo "⏭️  未找到带空格的目录，跳过"
fi

# 2. 删除旧的 cookies 目录
echo ""
echo "2️⃣ 删除旧的 cookies 目录..."
if [ -d "E:/SynapseAutomation/syn_backend/cookies" ]; then
    rm -rf "E:/SynapseAutomation/syn_backend/cookies"
    echo "✅ 已删除: syn_backend/cookies"
else
    echo "⏭️  未找到 syn_backend/cookies，跳过"
fi

# 3. 删除 config/cookies 目录
echo ""
echo "3️⃣ 删除 config/cookies 目录..."
if [ -d "E:/SynapseAutomation/syn_backend/config/cookies" ]; then
    rm -rf "E:/SynapseAutomation/syn_backend/config/cookies"
    echo "✅ 已删除: syn_backend/config/cookies"
else
    echo "⏭️  未找到 config/cookies，跳过"
fi

# 4. 可选：删除根目录 .env（如果 syn_backend/.env 已配置完整）
echo ""
echo "4️⃣ 检查根目录 .env..."
if [ -f "E:/SynapseAutomation/.env" ]; then
    echo "⚠️  发现根目录 .env 文件"
    echo "   建议：如果 syn_backend/.env 已配置完整，可以删除根目录 .env"
    echo "   保留：作为备份也可以"
    # read -p "   是否删除根目录 .env？(y/n): " answer
    # if [ "$answer" == "y" ]; then
    #     rm "E:/SynapseAutomation/.env"
    #     echo "✅ 已删除: 根目录 .env"
    # else
    #     echo "⏭️  保留根目录 .env"
    # fi
else
    echo "⏭️  未找到根目录 .env，跳过"
fi

echo ""
echo "=========================================="
echo "✅ 清理完成！"
echo "=========================================="
echo ""
echo "📊 当前 Cookie 目录结构："
echo "   ✅ syn_backend/cookiesFile/        ← 主目录（使用中）"
echo ""
echo "📊 环境变量配置："
echo "   ✅ syn_backend/.env                ← 主配置文件"
echo "   ⚠️  根目录 .env                     ← 备份/回退（可选）"
echo ""
echo "📊 Playwright 浏览器："
echo "   ✅ .playwright-browsers            ← 正常使用"
echo ""
