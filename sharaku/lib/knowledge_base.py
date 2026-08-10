"""
知识库模块 - 读取本地 Markdown 笔记，为投资顾问提供个人经验上下文

设计要点：
- 扫描指定目录下的 .md / .markdown 文件（递归）
- 带 mtime 缓存，文件未变更时不重复读盘
- 知识库总量小于阈值时全量注入；超过阈值时按关键词相关度排序取 TopK
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from loguru import logger

# 全量注入的字符上限（约等于 15k~20k tokens，留足空间给行情数据和对话历史）
FULL_INJECT_CHAR_LIMIT = 60000

# 超限时按相关度选取的文档数上限
TOP_K_DOCS = 8

# 单篇文档截断长度（防止某一篇超长文档挤占全部预算）
PER_DOC_CHAR_LIMIT = 12000

_MD_EXTENSIONS = (".md", ".markdown")

# 中英文分词用的简单正则：连续英文数字视为一个词，中文按单字切
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_'-]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]")

# 检索时忽略的高频无意义词
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of", "in",
    "on", "for", "and", "or", "but", "if", "it", "this", "that", "with", "as",
    "at", "by", "from", "not", "no", "do", "does", "did", "can", "could", "will",
    "would", "should", "i", "you", "he", "she", "we", "they", "my", "me",
    "的", "了", "是", "在", "和", "有", "我", "你", "他", "她", "它", "这", "那",
    "个", "上", "下", "不", "也", "就", "都", "很", "还", "被", "把", "给", "对",
    "吗", "呢", "吧", "啊", "什么", "怎么",
}


@dataclass
class KnowledgeDoc:
    """一篇知识库文档"""

    path: str  # 相对知识库根目录的路径
    title: str  # 文档标题（首个 H1，缺失则用文件名）
    content: str  # 正文
    mtime: float  # 文件修改时间

    @property
    def char_count(self) -> int:
        return len(self.content)


def _tokenize(text: str) -> List[str]:
    """粗粒度分词，返回小写 token 列表"""
    tokens = [tk.lower() for tk in _TOKEN_RE.findall(text)]
    return [tk for tk in tokens if tk not in _STOPWORDS]


def _extract_title(content: str, fallback: str) -> str:
    """从 markdown 内容中提取首个 H1 作为标题"""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


class KnowledgeBase:
    """本地 Markdown 知识库"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        # path -> (mtime, KnowledgeDoc)
        self._cache: Dict[str, Tuple[float, KnowledgeDoc]] = {}

    # ---------- 加载 ----------

    def _iter_md_files(self) -> List[str]:
        """递归收集知识库目录下所有 markdown 文件的绝对路径"""
        if not os.path.isdir(self.root_dir):
            return []

        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # 跳过隐藏目录
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                if name.lower().endswith(_MD_EXTENSIONS):
                    found.append(os.path.join(dirpath, name))
        return sorted(found)

    def load_all(self) -> List[KnowledgeDoc]:
        """加载全部文档（利用 mtime 缓存避免重复读盘）"""
        docs: List[KnowledgeDoc] = []
        seen_paths = set()

        for abs_path in self._iter_md_files():
            rel_path = os.path.relpath(abs_path, self.root_dir)
            seen_paths.add(rel_path)
            try:
                mtime = os.path.getmtime(abs_path)
            except OSError:
                continue

            cached = self._cache.get(rel_path)
            if cached and cached[0] == mtime:
                docs.append(cached[1])
                continue

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"知识库文档读取失败 {rel_path}: {e}")
                continue

            if not content.strip():
                continue

            doc = KnowledgeDoc(
                path=rel_path,
                title=_extract_title(content, os.path.splitext(os.path.basename(rel_path))[0]),
                content=content,
                mtime=mtime,
            )
            self._cache[rel_path] = (mtime, doc)
            docs.append(doc)

        # 清理已删除文件的缓存
        for stale in set(self._cache) - seen_paths:
            del self._cache[stale]

        return docs

    # ---------- 检索 ----------

    def _score(self, doc: KnowledgeDoc, query_tokens: List[str]) -> float:
        """基于关键词命中数打分，标题命中额外加权"""
        if not query_tokens:
            return 0.0

        content_lower = doc.content.lower()
        title_lower = doc.title.lower()

        score = 0.0
        for tk in set(query_tokens):
            hits = content_lower.count(tk)
            if hits:
                # 命中次数取对数抑制长文档优势
                score += 1.0 + min(hits, 10) * 0.1
            if tk in title_lower:
                score += 2.0
        return score

    def retrieve(self, query: str, extra_terms: Optional[List[str]] = None) -> List[KnowledgeDoc]:
        """
        根据查询检索相关文档。

        知识库总量在阈值内时返回全部（保证"综合参考"效果）；
        超限时按相关度取 TopK。
        """
        docs = self.load_all()
        if not docs:
            return []

        total_chars = sum(d.char_count for d in docs)
        if total_chars <= FULL_INJECT_CHAR_LIMIT:
            return docs

        tokens = _tokenize(query)
        for term in extra_terms or []:
            tokens.extend(_tokenize(term))

        scored = [(self._score(d, tokens), d) for d in docs]
        scored.sort(key=lambda x: (-x[0], x[1].path))

        selected: List[KnowledgeDoc] = []
        budget = FULL_INJECT_CHAR_LIMIT
        for score, doc in scored[:TOP_K_DOCS]:
            if budget <= 0:
                break
            selected.append(doc)
            budget -= min(doc.char_count, PER_DOC_CHAR_LIMIT)
        return selected

    # ---------- 渲染 ----------

    def build_context(self, query: str, extra_terms: Optional[List[str]] = None) -> str:
        """构造注入提示词的知识库文本块"""
        docs = self.retrieve(query, extra_terms)
        if not docs:
            return ""

        # 预算充足时全文注入。单篇截断只在总量超预算时才有意义——
        # 否则会白白丢掉长文档的末尾内容（通常是最新、最具操作性的部分）。
        total_chars = sum(d.char_count for d in docs)
        truncate = total_chars > FULL_INJECT_CHAR_LIMIT

        blocks = []
        for doc in docs:
            content = doc.content
            if truncate and len(content) > PER_DOC_CHAR_LIMIT:
                content = content[:PER_DOC_CHAR_LIMIT] + "\n...(文档过长已截断)"
            blocks.append(f"<document path=\"{doc.path}\" title=\"{doc.title}\">\n{content}\n</document>")

        return "\n\n".join(blocks)

    def stats(self) -> dict:
        """知识库概况，用于前端展示"""
        docs = self.load_all()
        return {
            "doc_count": len(docs),
            "total_chars": sum(d.char_count for d in docs),
            "docs": [{"path": d.path, "title": d.title, "chars": d.char_count} for d in docs],
        }
