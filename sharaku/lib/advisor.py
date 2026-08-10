"""
投资决策顾问模块 - LLM + 个人知识库 + 实时市场数据

工作流：
1. 采集标的的全维度事实数据（market_context）
2. 检索个人知识库中相关的经验笔记（knowledge_base）
3. 组装系统提示词，注入决策框架
4. 调用 LLM（OpenAI 兼容接口）流式生成建议

设计原则：
- 事实与判断分离：数据层由代码采集，判断层交给 LLM
- 知识库优先：用户的个人经验、纪律、教训优先于通用市场常识
- 明确可执行：输出必须包含具体价位、仓位、期权参数，而非泛泛而谈
"""

import os
from typing import Callable, Dict, Iterator, List, Optional

from loguru import logger

from sharaku.lib.knowledge_base import KnowledgeBase
from sharaku.lib.market_context import build_market_context, render_market_context

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_TOKENS = 8000

# 对话历史保留的最大轮数（防止上下文无限增长）
MAX_HISTORY_TURNS = 12


SYSTEM_PROMPT_TEMPLATE = """你是一位资深的投资决策顾问，专精于股票估值、入场时机判断和期权策略设计。你正在辅助一位有经验的个人投资者做决策。

## 你的核心任务

回答用户关于标的的问题，重点覆盖：
1. **好价格判断** — 当前价格相对内在价值、历史区间、技术位置是否具备吸引力
2. **入场点设计** — 给出分批建仓的具体价位与触发条件，而不是模糊的"可以考虑"
3. **期权策略** — 基于真实期权链数据，给出具体的行权价、到期日、预期权利金和年化收益
4. **风险边界** — 明确止损位、最大可承受回撤、失效条件

## 决策纪律（必须遵守）

- **知识库优先**：下方 `<knowledge_base>` 中是用户的个人投资笔记、纪律和历史教训。当知识库中的原则与通用市场常识冲突时，以知识库为准，并明确指出你在遵循哪条个人原则。
- **引用事实**：所有判断必须建立在 `<market_data>` 提供的数据上。引用具体数字，不要编造。
- **数据缺失要声明**：若某项数据为 N/A，明确说"该数据不可用"，不要脑补。
- **给出可执行参数**：期权建议必须包含行权价、到期日、权利金、年化收益率、被行权后的成本。入场建议必须包含具体价位和仓位比例。
- **主动指出矛盾**：当技术面、基本面、统计预测互相冲突时，明确指出分歧所在，并说明你倾向哪一边及原因。
- **不做保证**：使用概率化表述（"若…则…"、"概率上偏向"），不使用"一定"、"必然"。

## 输出格式

用 Markdown 组织回答。根据问题复杂度选择结构：
- 简单追问：直接回答，2-3 段
- 完整决策请求：用小标题分节（结论先行 → 依据 → 具体操作 → 风险与失效条件）

结论放最前面，让用户不看细节也能拿到答案。

{knowledge_section}

<market_data>
{market_data}
</market_data>

当前时间：{now}
"""

KNOWLEDGE_SECTION_TEMPLATE = """<knowledge_base>
以下是用户的个人投资笔记与经验总结。这些是用户经过实践检验的原则，优先级高于通用市场常识。

{knowledge}
</knowledge_base>"""

NO_KNOWLEDGE_SECTION = """<knowledge_base>
（知识库为空。用户尚未添加个人投资笔记，请基于市场数据与通用投资框架给出建议，并在回答末尾提示用户可以添加个人笔记以获得更贴合其风格的建议。）
</knowledge_base>"""


class AdvisorConfigError(RuntimeError):
    """LLM 配置缺失或不合法"""


class InvestmentAdvisor:
    """投资决策顾问"""

    def __init__(
        self,
        knowledge_dir: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.knowledge_base = KnowledgeBase(knowledge_dir)
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "")
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        # temperature 留空表示不发送该参数。部分模型（如经 Bedrock 的 claude-opus-5）
        # 已废弃 temperature，发送会直接报 400。
        raw_temp = os.getenv("LLM_TEMPERATURE", "")
        try:
            self.temperature: Optional[float] = float(raw_temp) if raw_temp.strip() else None
        except ValueError:
            self.temperature = None
        self._client = None
        # 记录本进程内已确认不支持 temperature 的模型，避免每次请求都先失败一次
        self._temperature_unsupported = False

    # ---------- LLM 客户端 ----------

    def _get_client(self):
        """惰性创建 OpenAI 兼容客户端"""
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise AdvisorConfigError(
                "未配置 LLM_API_KEY，请在 .env 中设置后重启服务"
            )

        try:
            from openai import OpenAI
        except ImportError as e:
            raise AdvisorConfigError(
                "缺少 openai 依赖，请执行 pip install -r requirements.txt"
            ) from e

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ---------- 提示词组装 ----------

    def build_system_prompt(
        self,
        ticker: str,
        question: str,
        cost_basis: float = 0,
        horizon_days: int = 30,
        cached_context: Optional[dict] = None,
    ) -> tuple[str, dict]:
        """
        组装系统提示词。

        Returns:
            (system_prompt, market_context) — market_context 可缓存供后续追问复用
        """
        from datetime import datetime

        ctx = cached_context or build_market_context(
            ticker, cost_basis=cost_basis, horizon_days=horizon_days
        )
        market_data = render_market_context(ctx)

        # 检索知识库：查询词包含用户问题 + 标的信息，提高命中率
        extra_terms = [ticker]
        if ctx.get("name"):
            extra_terms.append(str(ctx["name"]))
        fundamentals = ctx.get("fundamentals") or {}
        for key in ("sector", "industry"):
            if fundamentals.get(key):
                extra_terms.append(str(fundamentals[key]))

        knowledge = self.knowledge_base.build_context(question, extra_terms=extra_terms)
        knowledge_section = (
            KNOWLEDGE_SECTION_TEMPLATE.format(knowledge=knowledge)
            if knowledge
            else NO_KNOWLEDGE_SECTION
        )

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            knowledge_section=knowledge_section,
            market_data=market_data,
            now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return prompt, ctx

    @staticmethod
    def _trim_history(history: List[dict]) -> List[dict]:
        """截断过长的对话历史，保留最近若干轮"""
        if not history:
            return []
        # 每轮 = user + assistant，保留最近 MAX_HISTORY_TURNS 轮
        max_messages = MAX_HISTORY_TURNS * 2
        trimmed = history[-max_messages:]
        # 确保第一条是 user，避免 role 交替被破坏
        while trimmed and trimmed[0].get("role") != "user":
            trimmed = trimmed[1:]
        return trimmed

    @staticmethod
    def _is_unsupported_param_error(err: Exception, param: str) -> bool:
        """判断异常是否为「该模型不支持某参数」"""
        msg = str(err).lower()
        return param in msg and any(
            kw in msg for kw in ("deprecated", "unsupported", "not supported", "unexpected")
        )

    def _create_stream(self, messages: List[dict]):
        """
        创建流式响应。

        不同网关/模型对可选参数的支持不一致（例如经 Bedrock 的 claude-opus-5
        已废弃 temperature），因此遇到「参数不支持」时自动去掉该参数重试一次，
        而不是把可恢复的配置问题当成硬错误抛给用户。
        """
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if self.temperature is not None and not self._temperature_unsupported:
            kwargs["temperature"] = self.temperature

        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if "temperature" in kwargs and self._is_unsupported_param_error(e, "temperature"):
                logger.warning(f"模型 {self.model} 不支持 temperature，已去除该参数重试")
                self._temperature_unsupported = True
                kwargs.pop("temperature")
                return client.chat.completions.create(**kwargs)
            raise

    # ---------- 流式对话 ----------

    def stream_chat(
        self,
        ticker: str,
        question: str,
        cost_basis: float = 0,
        horizon_days: int = 30,
        history: Optional[List[dict]] = None,
        cached_context: Optional[dict] = None,
        on_context: Optional[Callable[[dict], None]] = None,
    ) -> Iterator[Dict[str, str]]:
        """
        流式生成投资建议。

        Args:
            on_context: 市场上下文采集完成后的回调，用于外部缓存。
                        使用回调而非实例属性，避免多请求共享实例时的状态竞争。

        Yields:
            {"type": "meta", ...} 元信息（一次）
            {"type": "delta", "content": ...} 增量文本
            {"type": "done"} 结束
            {"type": "error", "message": ...} 错误
        """
        try:
            client = self._get_client()
        except AdvisorConfigError as e:
            yield {"type": "error", "message": str(e)}
            return

        try:
            system_prompt, ctx = self.build_system_prompt(
                ticker, question, cost_basis, horizon_days, cached_context
            )
        except Exception as e:
            logger.error(f"上下文组装失败 {ticker}: {e}")
            yield {"type": "error", "message": f"市场数据采集失败: {e}"}
            return

        if not ctx.get("success"):
            yield {"type": "error", "message": ctx.get("error", "市场数据不可用")}
            return

        if on_context and cached_context is None:
            try:
                on_context(ctx)
            except Exception as e:
                logger.debug(f"上下文回调失败: {e}")

        kb_stats = self.knowledge_base.stats()
        yield {
            "type": "meta",
            "ticker": ctx.get("ticker"),
            "name": ctx.get("name"),
            "current_price": ctx.get("price", {}).get("current_price"),
            "knowledge_docs": kb_stats["doc_count"],
            "model": self.model,
        }

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._trim_history(history or []))
        messages.append({"role": "user", "content": question})

        try:
            stream = self._create_stream(messages)
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            yield {"type": "error", "message": f"模型调用失败: {e}"}
            return

        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield {"type": "delta", "content": content}
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"LLM 流式读取中断: {e}")
            yield {"type": "error", "message": f"模型响应中断: {e}"}

    # ---------- 知识库信息 ----------

    def knowledge_stats(self) -> dict:
        return self.knowledge_base.stats()
