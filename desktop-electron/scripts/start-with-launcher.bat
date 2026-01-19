@echo off
:: 启动 Synapse Automation 并显示启动管理器
:: 用于开发环境测试

echo ========================================
echo Synapse Automation - Launcher Mode
echo ========================================

set SYNAPSE_SHOW_LAUNCHER=1
set SYNAPSE_START_SERVICES=0

cd /d "%~dp0..\"
npm start
