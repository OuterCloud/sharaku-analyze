"""Tests for KnowledgeBase"""

import os
import time

import pytest

from sharaku.lib import knowledge_base as kb_mod
from sharaku.lib.knowledge_base import KnowledgeBase


@pytest.fixture
def kb_dir(tmp_path):
    """临时知识库目录"""
    d = tmp_path / "knowledge"
    d.mkdir()
    return d


def _write(path, content):
    path.write_text(content, encoding="utf-8")


class TestKnowledgeBaseLoading:
    def test_empty_dir_returns_no_docs(self, kb_dir):
        kb = KnowledgeBase(str(kb_dir))
        assert kb.load_all() == []
        assert kb.build_context("任何问题") == ""

    def test_missing_dir_is_tolerated(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "does-not-exist"))
        assert kb.load_all() == []
        assert kb.stats()["doc_count"] == 0

    def test_loads_markdown_files(self, kb_dir):
        _write(kb_dir / "a.md", "# 投资原则\n只在低估时买入")
        _write(kb_dir / "b.markdown", "# 期权手册\nSell Put 纪律")
        kb = KnowledgeBase(str(kb_dir))
        docs = kb.load_all()

        assert len(docs) == 2
        titles = {d.title for d in docs}
        assert titles == {"投资原则", "期权手册"}

    def test_ignores_non_markdown(self, kb_dir):
        _write(kb_dir / "note.md", "# 有效\n内容")
        _write(kb_dir / "data.txt", "无效")
        _write(kb_dir / "sheet.csv", "a,b")
        kb = KnowledgeBase(str(kb_dir))
        assert len(kb.load_all()) == 1

    def test_ignores_hidden_files_and_dirs(self, kb_dir):
        _write(kb_dir / ".hidden.md", "# 隐藏")
        hidden_dir = kb_dir / ".git"
        hidden_dir.mkdir()
        _write(hidden_dir / "inner.md", "# 内部")
        _write(kb_dir / "visible.md", "# 可见")

        kb = KnowledgeBase(str(kb_dir))
        docs = kb.load_all()
        assert len(docs) == 1
        assert docs[0].title == "可见"

    def test_recursive_subdirectories(self, kb_dir):
        sub = kb_dir / "watchlist"
        sub.mkdir()
        _write(sub / "AAPL.md", "# 苹果笔记\n持仓逻辑")
        _write(kb_dir / "root.md", "# 根笔记")

        kb = KnowledgeBase(str(kb_dir))
        docs = kb.load_all()
        assert len(docs) == 2
        paths = {d.path for d in docs}
        assert os.path.join("watchlist", "AAPL.md") in paths

    def test_skips_blank_files(self, kb_dir):
        _write(kb_dir / "blank.md", "   \n\n  ")
        _write(kb_dir / "real.md", "# 有内容")
        kb = KnowledgeBase(str(kb_dir))
        assert len(kb.load_all()) == 1

    def test_title_falls_back_to_filename(self, kb_dir):
        _write(kb_dir / "no-heading.md", "正文没有标题行")
        kb = KnowledgeBase(str(kb_dir))
        assert kb.load_all()[0].title == "no-heading"


class TestKnowledgeBaseCache:
    def test_reuses_cache_when_unchanged(self, kb_dir):
        _write(kb_dir / "a.md", "# 原始\n内容")
        kb = KnowledgeBase(str(kb_dir))
        first = kb.load_all()[0]
        second = kb.load_all()[0]
        # 未修改时应返回同一对象（走缓存）
        assert first is second

    def test_reloads_when_file_modified(self, kb_dir):
        f = kb_dir / "a.md"
        _write(f, "# 原始")
        kb = KnowledgeBase(str(kb_dir))
        assert kb.load_all()[0].title == "原始"

        # 确保 mtime 变化（文件系统精度可能是秒级）
        time.sleep(0.01)
        _write(f, "# 更新后")
        os.utime(f, (time.time() + 1, time.time() + 1))

        assert kb.load_all()[0].title == "更新后"

    def test_evicts_deleted_files(self, kb_dir):
        f = kb_dir / "a.md"
        _write(f, "# 待删除")
        kb = KnowledgeBase(str(kb_dir))
        assert len(kb.load_all()) == 1

        f.unlink()
        assert kb.load_all() == []
        assert kb._cache == {}


class TestKnowledgeBaseRetrieval:
    def test_injects_all_docs_when_under_limit(self, kb_dir):
        for i in range(5):
            _write(kb_dir / f"doc{i}.md", f"# 文档{i}\n内容{i}")
        kb = KnowledgeBase(str(kb_dir))
        # 总量远小于阈值，应全量返回而不做筛选
        assert len(kb.retrieve("完全不相关的查询")) == 5

    def test_ranks_by_relevance_when_over_limit(self, kb_dir, monkeypatch):
        # 压低阈值触发检索路径
        monkeypatch.setattr(kb_mod, "FULL_INJECT_CHAR_LIMIT", 200)
        monkeypatch.setattr(kb_mod, "TOP_K_DOCS", 2)

        _write(kb_dir / "options.md", "# 期权策略\n" + "Sell Put 行权价选择 " * 10)
        _write(kb_dir / "value.md", "# 价值投资\n" + "自由现金流折现 " * 10)
        _write(kb_dir / "misc.md", "# 杂记\n" + "随手记录 " * 10)

        kb = KnowledgeBase(str(kb_dir))
        docs = kb.retrieve("Sell Put 应该怎么选行权价")
        assert len(docs) <= 2
        assert docs[0].title == "期权策略"

    def test_build_context_wraps_documents(self, kb_dir):
        _write(kb_dir / "a.md", "# 我的纪律\n不追高")
        kb = KnowledgeBase(str(kb_dir))
        ctx = kb.build_context("入场纪律")

        assert '<document path="a.md"' in ctx
        assert 'title="我的纪律"' in ctx
        assert "不追高" in ctx
        assert ctx.endswith("</document>")

    def test_truncates_oversized_doc_only_when_over_budget(self, kb_dir, monkeypatch):
        # 仅当总量超出全量注入预算时，才对单篇做截断
        monkeypatch.setattr(kb_mod, "FULL_INJECT_CHAR_LIMIT", 100)
        monkeypatch.setattr(kb_mod, "PER_DOC_CHAR_LIMIT", 50)
        _write(kb_dir / "long.md", "# 超长\n" + "内容" * 500)
        kb = KnowledgeBase(str(kb_dir))
        ctx = kb.build_context("查询")
        assert "文档过长已截断" in ctx

    def test_keeps_long_doc_intact_when_budget_allows(self, kb_dir):
        # 预算充足时长文档必须完整注入，不能丢掉末尾内容
        body = "内容" * 3000  # 6000 字符，远小于 60000 预算
        _write(kb_dir / "journal.md", "# 交易日志\n" + body + "\n最后一条教训")
        kb = KnowledgeBase(str(kb_dir))
        ctx = kb.build_context("教训")

        assert "文档过长已截断" not in ctx
        assert "最后一条教训" in ctx


class TestKnowledgeBaseStats:
    def test_stats_shape(self, kb_dir):
        _write(kb_dir / "a.md", "# 甲\n12345")
        _write(kb_dir / "b.md", "# 乙\n67890")
        kb = KnowledgeBase(str(kb_dir))
        stats = kb.stats()

        assert stats["doc_count"] == 2
        assert stats["total_chars"] > 0
        assert len(stats["docs"]) == 2
        assert set(stats["docs"][0]) == {"path", "title", "chars"}
