"""Shared pytest fixtures"""

import pytest

# 顾问模块会读取的环境变量。测试必须与宿主环境隔离，
# 否则开发机上存在的真实 key 会让"未配置"场景的断言失效，
# 甚至触发真实的网络调用。
_LLM_ENV_VARS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "KNOWLEDGE_DIR",
)


@pytest.fixture(autouse=True)
def isolate_llm_env(monkeypatch):
    """清除所有 LLM 相关环境变量，保证测试可复现"""
    for name in _LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
