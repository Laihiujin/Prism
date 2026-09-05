@echo off
rem Prism 本地一键部署入口（Windows）。直接调用 PowerShell 引导器，避免 cmd 语法受限。
rem 用法:
rem   deploy.cmd              = 启动部署 Web UI（默认 127.0.0.1:8440）
rem   deploy.cmd full         = 无界面一键部署（plan->install-tools->bootstrap->start）
rem   deploy.cmd plan|status|start|stop|bootstrap|install-tools
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
