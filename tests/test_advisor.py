"""Tests for InvestmentAdvisor"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sharaku.lib.advisor import AdvisorConfigError, InvestmentAdvisor


@pytest.fixture
def kb_dir(tmp_path):
    d = tmp_path / "knowledge"
    d.mkdir()
    (d / "principles.md").write_text(
        "# 我的投资纪律\n只在 RSI < 40 时建仓，单一标的不超过 15% 仓位。",
        encoding="utf-8",
    )
    return str(d)


def _fake_context(ticker="AAPL", success=True):
    """构造 build_market_context 的返回值"""
    if not success:
        return {"success": False, "error": "未找到数据", "ticker": ticker}
    return {
        "success": True,
        "ticker": ticker,
        "name": "Apple Inc.",
        "as_of": "2026-08-08 10:00:00",
        "position": {"cost_basis": None, "unrealized_pnl_pct": None},
        "price": {"current_price": 313.0, "currency": "USD"},
        "levels": {},
        "technical": None,
        "fundamentals": {"sector": "Technology", "industry": "Consumer Electronics"},
        "analyst": {},
        "forecast": None,
        "options": None,
        "earnings": None,
        "wheel": None,
        "wheel_unavailable_reason": None,
    }


def _make_stream(chunks):
    """构造 OpenAI 流式响应的 mock"""
    events = []
    for c in chunks:
        events.append(
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=c))])
        )
    return events


class TestAdvisorConfig:
    def test_missing_api_key_reports_not_configured(self, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="")
        assert advisor.is_configured() is False

    def test_missing_api_key_raises_on_client_creation(self, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="")
        with pytest.raises(AdvisorConfigError, match="LLM_API_KEY"):
            advisor._get_client()

    def test_stream_yields_error_when_unconfigured(self, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="")
        events = list(advisor.stream_chat("AAPL", "现在是好价格吗"))
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert "LLM_API_KEY" in events[0]["message"]

    def test_explicit_params_take_precedence(self, kb_dir):
        advisor = InvestmentAdvisor(
            knowledge_dir=kb_dir, api_key="sk-test", base_url="https://x/v1", model="m1"
        )
        assert advisor.is_configured() is True
        assert advisor.base_url == "https://x/v1"
        assert advisor.model == "m1"


class TestSystemPrompt:
    @patch("sharaku.lib.advisor.build_market_context")
    def test_prompt_includes_knowledge_and_market_data(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        prompt, ctx = advisor.build_system_prompt("AAPL", "现在是好价格吗")

        assert "<knowledge_base>" in prompt
        assert "只在 RSI < 40 时建仓" in prompt
        assert "<market_data>" in prompt
        assert "AAPL" in prompt
        assert ctx["success"] is True

    @patch("sharaku.lib.advisor.build_market_context")
    def test_empty_knowledge_base_uses_placeholder(self, mock_ctx, tmp_path):
        mock_ctx.return_value = _fake_context()
        empty = tmp_path / "empty"
        empty.mkdir()
        advisor = InvestmentAdvisor(knowledge_dir=str(empty), api_key="sk-test")
        prompt, _ = advisor.build_system_prompt("AAPL", "问题")

        assert "知识库为空" in prompt

    @patch("sharaku.lib.advisor.build_market_context")
    def test_cached_context_skips_collection(self, mock_ctx, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        cached = _fake_context()
        advisor.build_system_prompt("AAPL", "问题", cached_context=cached)
        mock_ctx.assert_not_called()


class TestHistoryTrimming:
    def test_empty_history(self):
        assert InvestmentAdvisor._trim_history([]) == []

    def test_keeps_recent_turns(self):
        history = []
        for i in range(30):
            history.append({"role": "user", "content": f"q{i}"})
            history.append({"role": "assistant", "content": f"a{i}"})
        trimmed = InvestmentAdvisor._trim_history(history)

        assert len(trimmed) <= 24
        assert trimmed[0]["role"] == "user"
        assert trimmed[-1]["content"] == "a29"

    def test_drops_leading_assistant_message(self):
        history = [
            {"role": "assistant", "content": "orphan"},
            {"role": "user", "content": "q"},
        ]
        trimmed = InvestmentAdvisor._trim_history(history)
        assert trimmed[0]["role"] == "user"


class TestTemperatureHandling:
    def test_blank_temperature_is_omitted(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        assert advisor.temperature is None

    def test_invalid_temperature_is_omitted(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "not-a-number")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        assert advisor.temperature is None

    def test_valid_temperature_is_parsed(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        assert advisor.temperature == 0.7

    def test_temperature_sent_when_set(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake = MagicMock()
        fake.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake

        advisor._create_stream([{"role": "user", "content": "q"}])
        assert fake.chat.completions.create.call_args.kwargs["temperature"] == 0.3

    def test_temperature_absent_when_unset(self, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake = MagicMock()
        fake.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake

        advisor._create_stream([{"role": "user", "content": "q"}])
        assert "temperature" not in fake.chat.completions.create.call_args.kwargs

    def test_retries_without_temperature_on_deprecation_error(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")

        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            if "temperature" in kwargs:
                raise RuntimeError(
                    "BedrockException - `temperature` is deprecated for this model."
                )
            return _make_stream(["ok"])

        fake = MagicMock()
        fake.chat.completions.create.side_effect = create
        advisor._client = fake

        advisor._create_stream([{"role": "user", "content": "q"}])

        assert len(calls) == 2
        assert "temperature" in calls[0]
        assert "temperature" not in calls[1]
        # 后续请求应记住该模型不支持，不再重复失败
        assert advisor._temperature_unsupported is True

    def test_remembers_unsupported_across_calls(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        advisor._temperature_unsupported = True
        fake = MagicMock()
        fake.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake

        advisor._create_stream([{"role": "user", "content": "q"}])
        assert fake.chat.completions.create.call_count == 1
        assert "temperature" not in fake.chat.completions.create.call_args.kwargs

    def test_unrelated_error_is_not_retried(self, kb_dir, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake = MagicMock()
        fake.chat.completions.create.side_effect = RuntimeError("expired_key")
        advisor._client = fake

        with pytest.raises(RuntimeError, match="expired_key"):
            advisor._create_stream([{"role": "user", "content": "q"}])
        assert fake.chat.completions.create.call_count == 1

    def test_unsupported_param_detection(self):
        detect = InvestmentAdvisor._is_unsupported_param_error
        assert detect(RuntimeError("`temperature` is deprecated for this model"), "temperature")
        assert detect(RuntimeError("Unsupported parameter: temperature"), "temperature")
        assert detect(RuntimeError("unexpected keyword argument 'temperature'"), "temperature")
        # 与参数无关的错误不应误判
        assert not detect(RuntimeError("rate limit exceeded"), "temperature")
        assert not detect(RuntimeError("temperature must be between 0 and 2"), "temperature")


class TestStreamChat:
    @patch("sharaku.lib.advisor.build_market_context")
    def test_yields_meta_deltas_and_done(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_stream(["建议", "：观望"])
        advisor._client = fake_client

        events = list(advisor.stream_chat("AAPL", "现在是好价格吗"))
        types = [e["type"] for e in events]

        assert types[0] == "meta"
        assert types[-1] == "done"
        assert "".join(e["content"] for e in events if e["type"] == "delta") == "建议：观望"

    @patch("sharaku.lib.advisor.build_market_context")
    def test_meta_carries_knowledge_doc_count(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake_client

        meta = next(e for e in advisor.stream_chat("AAPL", "问题") if e["type"] == "meta")
        assert meta["knowledge_docs"] == 1
        assert meta["ticker"] == "AAPL"
        assert meta["current_price"] == 313.0

    @patch("sharaku.lib.advisor.build_market_context")
    def test_failed_context_yields_error(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context(success=False)
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        advisor._client = MagicMock()

        events = list(advisor.stream_chat("BADTICKER", "问题"))
        assert events[0]["type"] == "error"
        assert "未找到数据" in events[0]["message"]

    @patch("sharaku.lib.advisor.build_market_context")
    def test_llm_exception_yields_error(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("rate limited")
        advisor._client = fake_client

        events = list(advisor.stream_chat("AAPL", "问题"))
        assert events[-1]["type"] == "error"
        assert "rate limited" in events[-1]["message"]

    @patch("sharaku.lib.advisor.build_market_context")
    def test_on_context_callback_receives_context(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake_client

        received = []
        list(advisor.stream_chat("AAPL", "问题", on_context=received.append))

        assert len(received) == 1
        assert received[0]["ticker"] == "AAPL"

    @patch("sharaku.lib.advisor.build_market_context")
    def test_on_context_not_called_when_using_cache(self, mock_ctx, kb_dir):
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake_client

        received = []
        list(
            advisor.stream_chat(
                "AAPL", "追问", cached_context=_fake_context(), on_context=received.append
            )
        )
        assert received == []

    @patch("sharaku.lib.advisor.build_market_context")
    def test_history_is_passed_to_llm(self, mock_ctx, kb_dir):
        mock_ctx.return_value = _fake_context()
        advisor = InvestmentAdvisor(knowledge_dir=kb_dir, api_key="sk-test")
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _make_stream(["ok"])
        advisor._client = fake_client

        history = [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
        ]
        list(advisor.stream_chat("AAPL", "第二问", history=history))

        messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "第一问"
        assert messages[2]["content"] == "第一答"
        assert messages[-1]["content"] == "第二问"
