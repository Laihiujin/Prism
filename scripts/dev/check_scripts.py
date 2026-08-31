#!/usr/bin/env python3
"""
Prism 启动脚本清单检查工具
验证所有脚本和文档文件是否已创建
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

# 需要创建的文件清单
REQUIRED_FILES = {
    "启动脚本": [
        ("scripts/start.py", "跨平台Python启动脚本（推荐）"),
        ("scripts/start-server.py", "云服务器启动脚本（高级版，支持后台运行）"),
        ("scripts/start.ps1", "PowerShell启动脚本"),
        ("scripts/start-win.bat", "Windows批处理脚本"),
        ("scripts/setup-and-start.sh", "Linux/Mac Shell脚本"),
    ],
    "Nginx配置": [
        ("nginx.conf", "Nginx反向代理配置"),
        ("setup-nginx.sh", "Nginx自动配置脚本"),
    ],
    "文档": [
        ("README_SCRIPTS.md", "脚本完整清单（主文档）"),
        ("SCRIPTS_SUMMARY.md", "脚本总结和对比"),
        ("QUICK_START.md", "快速参考手册"),
        ("DEPLOY.md", "详细部署指南"),
        ("CLOUD_DEPLOYMENT.md", "云服务器完整部署指南"),
    ]
}

def check_files():
    """检查所有文件是否存在"""
    print("\n" + "="*60)
    print("Prism 启动脚本清单检查")
    print("="*60 + "\n")
    
    all_exist = True
    total_files = 0
    existing_files = 0
    
    for category, files in REQUIRED_FILES.items():
        print(f"\n📦 {category}")
        print("-" * 60)
        
        for filename, description in files:
            total_files += 1
            filepath = PROJECT_ROOT / filename
            exists = filepath.exists()
            
            if exists:
                existing_files += 1
                print(f"  ✅ {filename:<30} {description}")
            else:
                print(f"  ❌ {filename:<30} {description}")
                all_exist = False
    
    # 总结
    print("\n" + "="*60)
    print(f"检查结果: {existing_files}/{total_files} 文件已创建")
    print("="*60 + "\n")
    
    if all_exist:
        print("✨ 所有文件已成功创建！\n")
        print("🚀 快速开始:")
        print("   python scripts/start.py                              # 本地启动")
        print("   python scripts/start-server.py --background          # 云服务器启动")
        print("\n📖 查看文档:")
        print("   - README_SCRIPTS.md         主文档")
        print("   - QUICK_START.md            快速参考")
        print("   - CLOUD_DEPLOYMENT.md       云部署完整指南")
        print()
        return 0
    else:
        print("⚠️  部分文件缺失，请检查。\n")
        return 1

def show_help():
    """显示脚本使用方式"""
    print("\n" + "="*60)
    print("Prism 启动脚本使用指南")
    print("="*60 + "\n")
    
    print("📋 可用的启动方式:\n")
    
    print("1️⃣  最简单方式（推荐）")
    print("   python scripts/start.py\n")
    
    print("2️⃣  云服务器后台启动")
    print("   python scripts/start-server.py --background\n")
    
    print("3️⃣  Windows用户")
    print("   双击运行: scripts/start-win.bat\n")
    
    print("4️⃣  PowerShell用户")
    print("   .\\scripts/start.ps1\n")
    
    print("📖 文档说明:\n")
    
    print("README_SCRIPTS.md")
    print("   完整的脚本清单和使用指南（你应该先读这个）\n")
    
    print("QUICK_START.md")
    print("   快速参考手册，包含常用命令\n")
    
    print("CLOUD_DEPLOYMENT.md")
    print("   云服务器从零开始的完整部署指南\n")
    
    print("DEPLOY.md")
    print("   详细的部署指南和故障排除\n")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            show_help()
            sys.exit(0)
    
    exit_code = check_files()
    
    print("💡 提示:")
    print("   - 首次运行会自动下载依赖，请耐心等待")
    print("   - 查看 README_SCRIPTS.md 了解更多详情")
    print("   - 有问题请查看 QUICK_START.md 或 DEPLOY.md\n")
    
    sys.exit(exit_code)
