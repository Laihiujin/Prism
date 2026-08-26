@echo off
:: 启动 Prism 并显示启动管理器
:: 用于开发环境测试

echo ========================================
echo Prism - Launcher Mode
echo ========================================

set PRISM_SHOW_LAUNCHER=1
set PRISM_START_SERVICES=0

cd /d "%~dp0..\"
npm start
