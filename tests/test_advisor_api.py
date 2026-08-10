"""End-to-end tests for the advisor HTTP API (SSE streaming)"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import app as app_module

    return TestClient(app_module.app)


def _parse_sse(body: str) -> list:
    """解析 SSE 响应体为事件列表"""
    events = []
    for block in body.split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


class TestAdvisorStatus:
    def test_returns_config_and_knowledge(self, client):
        res = client.get("/api/advisor/status")
        assert res.status_code == 200
        data = res.json()

        assert data["success"] is True
        assert "configured" in data
        assert "model" in data
        assert "doc_count" in data["knowledge"]
        assert isinstance(data["knowledge"]["docs"], list)


class TestAdvisorChatValidation:
    def test_rejects_empty_ticker(self, client):
        res = client.post("/api/advisor/chat", data={"ticker": "  ", "question": "问题"})
        assert res.status_code == 400

    def test_rejects_empty_question(self, client):
        res = client.post("/api/advisor/chat", data={"ticker": "AAPL", "question": "   "})
        assert res.status_code == 400

    def test_requires_both_fields(self, client):
        res = client.post("/api/advisor/chat", data={"ticker": "AAPL"})
        assert res.status_code == 422


class TestAdvisorChatStreaming:
    def test_streams_sse_events(self, client):
        events = [
            {"type": "meta", "ticker": "AAPL", "name": "Apple", "current_price": 300.0,
             "knowledge_docs": 2, "model": "test-model"},
            {"type": "delta", "content": "结论："},
            {"type": "delta", "content": "当前不是好价格"},
            {"type": "done"},
        ]

        with patch("app.advisor.stream_chat", return_value=iter(events)):
            res = client.post(
                "/api/advisor/chat",
                data={"ticker": "aapl", "question": "现在是好价格吗"},
            )

        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")

        parsed = _parse_sse(res.text)
        assert [e["type"] for e in parsed] == ["meta", "delta", "delta", "done"]
        assert "".join(e["content"] for e in parsed if e["type"] == "delta") == "结论：当前不是好价格"

    def test_uppercases_ticker(self, client):
        with patch("app.advisor.stream_chat", return_value=iter([{"type": "done"}])) as mock:
            client.post("/api/advisor/chat", data={"ticker": "aapl", "question": "q"})
        assert mock.call_args.kwargs["ticker"] == "AAPL"

    def test_forwards_parameters(self, client):
        with patch("app.advisor.stream_chat", return_value=iter([{"type": "done"}])) as mock:
            client.post(
                "/api/advisor/chat",
                data={
                    "ticker": "AAPL",
                    "question": "追问",
                    "cost_basis": "250.5",
                    "horizon_days": "90",
                },
            )
        kwargs = mock.call_args.kwargs
        assert kwargs["cost_basis"] == 250.5
        assert kwargs["horizon_days"] == 90

    def test_parses_valid_history(self, client):
        history = [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
        ]
        with patch("app.advisor.stream_chat", return_value=iter([{"type": "done"}])) as mock:
            client.post(
                "/api/advisor/chat",
                data={"ticker": "AAPL", "question": "第二问", "history": json.dumps(history)},
            )
        assert mock.call_args.kwargs["history"] == history

    def test_drops_malformed_history_entries(self, client):
        history = [
            {"role": "user", "content": "有效"},
            {"role": "system", "content": "非法角色"},
            {"role": "assistant", "content": ""},
            {"role": "assistant"},
            "不是字典",
            {"role": "user", "content": 123},
        ]
        with patch("app.advisor.stream_chat", return_value=iter([{"type": "done"}])) as mock:
            client.post(
                "/api/advisor/chat",
                data={"ticker": "AAPL", "question": "q", "history": json.dumps(history)},
            )
        assert mock.call_args.kwargs["history"] == [{"role": "user", "content": "有效"}]

    def test_tolerates_invalid_history_json(self, client):
        with patch("app.advisor.stream_chat", return_value=iter([{"type": "done"}])) as mock:
            res = client.post(
                "/api/advisor/chat",
                data={"ticker": "AAPL", "question": "q", "history": "{not json"},
            )
        assert res.status_code == 200
        assert mock.call_args.kwargs["history"] == []

    def test_stream_exception_becomes_error_event(self, client):
        def boom(**kwargs):
            yield {"type": "meta", "ticker": "AAPL"}
            raise RuntimeError("upstream exploded")

        with patch("app.advisor.stream_chat", side_effect=boom):
            res = client.post("/api/advisor/chat", data={"ticker": "AAPL", "question": "q"})

        parsed = _parse_sse(res.text)
        assert parsed[-1]["type"] == "error"
        assert "upstream exploded" in parsed[-1]["message"]

    def test_error_event_from_advisor_is_forwarded(self, client):
        events = [{"type": "error", "message": "未配置 LLM_API_KEY"}]
        with patch("app.advisor.stream_chat", return_value=iter(events)):
            res = client.post("/api/advisor/chat", data={"ticker": "AAPL", "question": "q"})

        parsed = _parse_sse(res.text)
        assert parsed[0]["type"] == "error"
        assert "LLM_API_KEY" in parsed[0]["message"]

    def test_non_ascii_content_is_not_escaped(self, client):
        events = [{"type": "delta", "content": "看多（多头排列）"}, {"type": "done"}]
        with patch("app.advisor.stream_chat", return_value=iter(events)):
            res = client.post("/api/advisor/chat", data={"ticker": "AAPL", "question": "q"})

        # ensure_ascii=False，中文应原样传输而非 \uXXXX
        assert "看多（多头排列）" in res.text
