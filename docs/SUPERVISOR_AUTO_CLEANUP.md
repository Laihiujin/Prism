# Supervisor 自动清理功能

## 问题描述

当 SynapseAutomation 从旧路径（如 `D:\CC\SynapseAutomation`）迁移到新路径（如 `D:\syn\SynapseAutomation`）时，可能会出现以下问题：

1. **Celery Worker 节点名称冲突**：旧路径的 Celery Worker 进程仍在运行，导致出现 `DuplicateNodenameWarning` 警告
2. **端口占用冲突**：Redis (6379)、Backend (7000)、Playwright Worker (7001) 端口被旧进程占用
3. **服务无法启动**：新安装的 Supervisor 无法启动服务，因为端口已被占用

## 解决方案

### 自动进程清理机制

Supervisor 现在在启动服务前会自动检测并清理以下冲突进程：

1. **占用关键端口的进程**
   - Redis 端口 6379
   - Backend 端口 7000
   - Playwright Worker 端口 7001

2. **旧的 Celery Worker 进程**
   - 检测所有包含 `celery` 和 `worker` 关键字的进程
   - 排除当前 Supervisor 自己启动的子进程
   - 自动终止旧路径的 Celery Worker

### 实现细节

#### 新增方法：`_kill_conflicting_processes()`

```python
def _kill_conflicting_processes(self) -> None:
    """
    在启动前清理所有可能冲突的进程:
    1. 占用关键端口的进程 (6379, 7000, 7001)
    2. 旧的 Celery Worker 进程 (避免节点名称冲突)
    """
    logger.info("🧹 检查并清理冲突进程...")
    
    # 1. 清理端口占用
    critical_ports = [6379, 7000, 7001]
    for port in critical_ports:
        if self.is_port_in_use(port) and self.kill_port_conflict:
            pids = self._find_pids_by_port(port)
            if pids:
                logger.info(f"   清理端口 {port} 占用进程: {pids}")
                for pid in pids:
                    self._terminate_pid(pid)
                time.sleep(0.5)
    
    # 2. 清理所有 Celery Worker 进程
    try:
        import psutil
        celery_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()
                
                if 'celery' in cmdline_str and 'worker' in cmdline_str:
                    if proc.pid != os.getpid() and proc.pid not in [p.pid for p in self.manager.processes.values() if p.poll() is None]:
                        celery_pids.append(proc.pid)
                        logger.info(f"   发现旧的 Celery Worker: PID={proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if celery_pids:
            logger.warning(f"⚠️ 发现 {len(celery_pids)} 个旧的 Celery Worker 进程，正在清理...")
            for pid in celery_pids:
                if self._terminate_pid(pid):
                    logger.info(f"   ✅ 已终止 Celery Worker PID={pid}")
            time.sleep(1)
    except ImportError:
        logger.info("   ⚠️ psutil 未安装，跳过精确的 Celery 进程检测")
    
    logger.info("✅ 冲突进程清理完成")
```

#### 调用时机

在 `start_services()` 方法开始时自动调用：

```python
def start_services(self):
    """启动所有服务"""
    logger.info("=" * 60)
    logger.info("   SynapseAutomation Supervisor 启动")
    logger.info("=" * 60)

    # 清理可能冲突的进程（旧的 Celery Worker、占用端口的进程等）
    self._kill_conflicting_processes()

    env = self.build_env()
    # ... 后续启动逻辑
```

## 使用方式

### 默认行为

- **自动清理**：默认启用（`SUPERVISOR_KILL_PORT_CONFLICT=1`）
- Supervisor 启动时会自动检测并终止冲突进程
- 无需手动干预

### 禁用自动清理

如果需要禁用自动清理功能，可以设置环境变量：

```bash
set SUPERVISOR_KILL_PORT_CONFLICT=0
```

### 日志输出

启动时会看到类似以下日志：

```
[2026-01-15 14:35:29,000] [INFO] ============================================================
[2026-01-15 14:35:29,000] [INFO]    SynapseAutomation Supervisor 启动
[2026-01-15 14:35:29,000] [INFO] ============================================================
[2026-01-15 14:35:29,001] [INFO] 🧹 检查并清理冲突进程...
[2026-01-15 14:35:29,002] [INFO]    清理端口 6379 占用进程: [12345]
[2026-01-15 14:35:29,003] [INFO]    发现旧的 Celery Worker: PID=67890
[2026-01-15 14:35:29,004] [WARNING] ⚠️ 发现 1 个旧的 Celery Worker 进程，正在清理...
[2026-01-15 14:35:29,005] [INFO]    ✅ 已终止 Celery Worker PID=67890
[2026-01-15 14:35:30,006] [INFO] ✅ 冲突进程清理完成
```

## 优势

1. **自动化**：无需手动查找和终止旧进程
2. **智能检测**：精确识别 Celery Worker 进程，避免误杀
3. **安全性**：排除当前 Supervisor 自己的子进程
4. **可配置**：可通过环境变量控制是否启用
5. **日志完整**：详细记录清理过程，便于排查问题

## 注意事项

1. **依赖 psutil**：为了精确检测进程，建议安装 `psutil` 库
2. **权限要求**：终止进程可能需要管理员权限
3. **等待时间**：清理后会等待 1 秒，确保进程完全终止

## 故障排除

### 如果仍然出现节点名称冲突

1. 检查日志，确认是否成功清理了旧进程
2. 手动终止所有 `python.exe` 进程：
   ```powershell
   taskkill /F /IM python.exe
   ```
3. 重新启动 Supervisor

### 如果端口仍然被占用

1. 检查是否禁用了自动清理（`SUPERVISOR_KILL_PORT_CONFLICT=0`）
2. 手动释放端口：
   ```powershell
   # 查找占用端口的进程
   netstat -ano | findstr :6379
   # 终止进程
   taskkill /F /PID <PID>
   ```

## 更新日志

- **2026-01-15**：添加自动进程清理功能，解决路径迁移后的冲突问题
