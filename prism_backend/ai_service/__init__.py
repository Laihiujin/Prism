"""
AI 服务集成模块。

模型配置统一走 `/api/v1/ai` 的 model-configs（`ai_model_configs` 表），
通过 `ai_service.llm` / `ai_service.title_topic_generator` /
`metadata_generation_service` 等子模块按需加载；不再在包的
`__init__` 里导出任何被删除的 ModelManager / AIClient / providers。
"""
