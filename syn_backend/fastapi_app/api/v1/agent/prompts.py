"""
AI Orchestrator System Prompt
SynapseAutomation 矩阵调度系统

提示词统一加载模块 - 从 ai_prompts_unified.yaml 读取
"""

import yaml
from pathlib import Path
from fastapi_app.core.config import settings


def _load_unified_prompts():
    """从统一配置文件加载提示词"""
    try:
        config_path = settings.BASE_DIR / "config" / "ai_prompts_unified.yaml"

        # 如果统一配置不存在，回退到旧配置
        if not config_path.exists():
            config_path = settings.BASE_DIR / "config" / "ai_prompts.yaml"

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    except Exception as e:
        print(f"[Prompts] Failed to load prompts config: {e}")
        return {}


# 加载配置
_PROMPTS_CONFIG = _load_unified_prompts()


# ============================================
# 从配置文件提取系统提示词
# ============================================

def get_system_prompt(key: str) -> str:
    """
    从统一配置获取system_prompt

    支持的key:
    - 'manus_agent' - 矩阵调度系统
    - 'chat_assistant' - 聊天助手
    - 'title_generation' - 标题生成
    - 'description_generation' - 文案生成
    - 'tags_generation' - 标签生成
    - 'cover_generation' - 封面生成
    """
    # 尝试从 automation 模块加载
    if 'automation' in _PROMPTS_CONFIG and key in _PROMPTS_CONFIG['automation']:
        return _PROMPTS_CONFIG['automation'][key].get('system_prompt', '')

    # 尝试从 content_generation 模块加载
    if 'content_generation' in _PROMPTS_CONFIG and key in _PROMPTS_CONFIG['content_generation']:
        return _PROMPTS_CONFIG['content_generation'][key].get('system_prompt', '')

    # 尝试从根级别加载
    if key in _PROMPTS_CONFIG:
        config = _PROMPTS_CONFIG[key]
        if isinstance(config, dict):
            return config.get('system_prompt', '')

    return ''


# 保留原有的 SYSTEM_PROMPT 变量名以兼容旧代码
SYSTEM_PROMPT = get_system_prompt('manus_agent') or """你现在是 SynapseAutomation 的矩阵调度系统（AI Orchestrator）。
你的职责是根据素材库、账号库、平台规则，为用户生成可执行的发布计划脚本（JSON），并通过后端 API 调用实现真实的批量发布。

## 🎯 你的行动流程

1. 读取当前系统状态（素材库、账号池、已发布记录、平台发布规则）
2. 根据用户需求制定发布策略
3. 为每个视频生成独立标题、标签、描述（如用户要求）
4. 输出 SynapseAutomation 发布计划 DSL（JSON）
5. 调用后端接口 /agent/save-script 保存脚本
6. 如用户确认执行，再调用 /agent/execute-script 运行计划
7. 分析后端返回结果并总结

## 📦 系统能力

### 【数据访问】
- 可获取所有素材信息（未发布/已发布/已使用）
- 可获取全部账号列表（状态、可用性、用于哪个平台）
- 可查询某视频在哪些账号/平台已发布

### 【生成能力】
- 为每个素材生成独立标题
- 为不同平台生成不同文案（避免限流）
- 可根据用户自然语言生成完整矩阵发布计划

### 【规则执行】
必须严格遵守以下规则：
1. 同一个视频在同一个账号只能发一次
2. 同一个视频在同一个平台只能发一次
3. 同一个视频可以跨平台发布
4. 多个平台的账号不能使用完全相同的标题（保持差异度>10%）
5. 每条素材必须单独生成标题，不可复用
6. 发布时间必须生成随机区间以避免限流（默认30~300秒的随机错峰）
7. 若用户指定 dry-run 模式，只生成计划不执行
"""


# AI助手的用户提示模板
USER_PROMPT_TEMPLATE = """
## 当前系统状态

{context}

## 用户需求

{user_request}

## 请按照以下步骤处理

1. 分析用户需求
2. 获取系统上下文
3. 生成发布计划JSON
4. 展示计划给用户确认
5. 如用户同意，保存并执行脚本
6. 返回执行结果
"""


# ============================================
# OpenManus Agent 触发规则
# ============================================

OPENMANUS_TRIGGER_PROMPT = """
## 🤖 OpenManus Agent 触发规则

当任务涉及以下场景时，你必须触发 OpenManus Agent 来执行复杂的工具调用和任务编排：

### 触发条件（任一满足即触发）

1. **多账号批量操作**
   - 用户要求为多个账号创建发布计划
   - 涉及账号筛选、分组、分配任务

2. **多素材批量处理**
   - 需要处理多个视频素材
   - 为每个素材生成独立的标题、标签、描述

3. **复杂排期规划**
   - 需要计算发布时间、错峰策略
   - 涉及时间冲突检测和自动调整

4. **跨平台分发**
   - 同一素材需要发布到多个平台
   - 需要生成平台特定的文案

5. **脚本生成与执行**
   - 需要生成 SynapseAutomation DSL JSON 脚本
   - 需要保存脚本并执行

6. **系统状态查询与分析**
   - 需要查询账号状态、素材使用情况
   - 需要分析历史发布数据

### 非触发场景（直接回答）

以下场景**不需要**触发 OpenManus，直接回答：

1. 用户询问系统功能、使用方法
2. 用户要求解释某个概念
3. 简单的状态查询（单个账号、单个视频）
4. 一般性对话和问候
"""


# 扩展系统 Prompt，包含 OpenManus 规则
SYSTEM_PROMPT_WITH_OPENMANUS = SYSTEM_PROMPT + """

---

""" + OPENMANUS_TRIGGER_PROMPT
