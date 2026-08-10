import { useEffect, useRef, useState } from "react";
import {
  AdvisorEvent,
  AdvisorStatus,
  ChatMessage,
  getAdvisorStatus,
  streamAdvisorChat,
} from "../api/advisor";
import { useI18n } from "../i18n/context";
import { copyToClipboard } from "../utils/clipboard";
import { renderMarkdown } from "../utils/markdown";
import {
  distanceFromBottom,
  isNearBottom,
  readWindowScrollMetrics,
  resolveJumpButtonVisible,
  resolvePinState,
} from "../utils/scroll";
import StockSearch from "./StockSearch";
import Watchlist from "./Watchlist";

/** 预设问题模板的 i18n key */
const PRESET_KEYS = [
  "advisor.preset.goodPrice",
  "advisor.preset.entry",
  "advisor.preset.options",
  "advisor.preset.risk",
  "advisor.preset.full",
] as const;

interface Turn {
  role: "user" | "assistant";
  content: string;
  /** 助手消息是否仍在流式接收 */
  streaming?: boolean;
  error?: string;
}

function MessageBubble({ turn }: { turn: Turn }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await copyToClipboard(turn.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 复制失败静默处理，用户可手动选中
    }
  }

  if (turn.role === "user") {
    return (
      <div className="advisor-msg advisor-msg-user">
        <div className="advisor-msg-body">{turn.content}</div>
      </div>
    );
  }

  return (
    <div className="advisor-msg advisor-msg-assistant">
      <div className="advisor-msg-header">
        <span className="advisor-msg-role">{t("advisor.assistant")}</span>
        {!turn.streaming && turn.content && (
          <button className="btn-copy" onClick={handleCopy}>
            {copied ? t("single.result.copied") : t("single.result.copy")}
          </button>
        )}
      </div>
      {turn.error ? (
        <div className="error-message">{turn.error}</div>
      ) : (
        <div
          className="advisor-msg-body markdown-body"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(turn.content) }}
        />
      )}
      {turn.streaming && (
        <div className="advisor-typing">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  );
}

export default function AdvisorTab() {
  const [ticker, setTicker] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [horizonDays, setHorizonDays] = useState(30);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState<AdvisorStatus | null>(null);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [error, setError] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  /** 用户是否"贴"在底部。用 ref 而非 state，避免滚动时频繁重渲染 */
  const pinnedRef = useRef(true);
  const lastScrollYRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const { t } = useI18n();

  // 载入配置状态与知识库概况
  useEffect(() => {
    getAdvisorStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  /** 当前 Tab 是否可见（非激活 Tab 用 display:none，此时 offsetParent 为 null） */
  const isVisible = () => rootRef.current?.offsetParent !== null;

  const scrollToBottom = (smooth = false) => {
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: smooth ? "smooth" : "auto",
    });
  };

  // 跟踪用户是否主动滚离底部：向上滚开后停止自动跟随，改为提示"跳到最新"
  useEffect(() => {
    function onScroll() {
      if (!isVisible()) return;
      const metrics = readWindowScrollMetrics();
      const currentScrollY = metrics.scrollY;

      const pinned = resolvePinState({
        atBottom: isNearBottom(metrics),
        previousScrollY: lastScrollYRef.current,
        currentScrollY,
        wasPinned: pinnedRef.current,
      });
      lastScrollYRef.current = currentScrollY;
      pinnedRef.current = pinned;

      // 按钮显隐独立于跟随状态判断，并使用迟滞阈值避免边界抖动
      const distance = distanceFromBottom(metrics);
      setShowJumpToLatest((visible) =>
        pinned ? false : resolveJumpButtonVisible(distance, visible)
      );
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // 新内容到达时跟随底部。
  // 关键点：
  // 1) 用即时滚动而非 smooth——流式每个 token 都会触发本效应，smooth 动画会
  //    互相打断，导致页面停在不可预期的位置；
  // 2) 仅在用户"贴底"时跟随，否则会把正在往上翻阅的用户强行拽回；
  // 3) 滚到文档真实底部而非锚点视口底部，避免内容被 sticky 输入框遮挡；
  // 4) Tab 不可见时不滚动，否则会劫持用户当前所在页面的滚动位置。
  useEffect(() => {
    if (!pinnedRef.current || !isVisible()) return;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    // 合并同一帧内的多次内容更新，避免逐字符触发布局计算
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      scrollToBottom(false);
    });
  }, [turns]);

  // 卸载时中断请求并取消待执行的滚动
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  function handleJumpToLatest() {
    pinnedRef.current = true;
    setShowJumpToLatest(false);
    scrollToBottom(true);
  }

  function handleSelectTicker(tk: string) {
    if (tk !== ticker) {
      // 切换标的时清空对话，避免上下文串台
      setTurns([]);
      setError("");
    }
    setTicker(tk);
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q) return;
    if (!ticker) {
      setError(t("common.error.selectStock"));
      return;
    }
    if (streaming) return;

    setError("");
    setQuestion("");

    // 发送前的历史（不含本轮）
    const history: ChatMessage[] = turns
      .filter((tn) => !tn.error && tn.content.trim())
      .map((tn) => ({ role: tn.role, content: tn.content }));

    setTurns((prev) => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "", streaming: true },
    ]);
    setStreaming(true);
    // 主动发问意味着想看新回答，重新恢复跟随
    pinnedRef.current = true;
    setShowJumpToLatest(false);

    const controller = new AbortController();
    abortRef.current = controller;

    /** 更新最后一条助手消息 */
    const updateLast = (patch: Partial<Turn>) => {
      setTurns((prev) => {
        const next = [...prev];
        const idx = next.length - 1;
        if (idx >= 0 && next[idx].role === "assistant") {
          next[idx] = { ...next[idx], ...patch };
        }
        return next;
      });
    };

    const appendDelta = (chunk: string) => {
      setTurns((prev) => {
        const next = [...prev];
        const idx = next.length - 1;
        if (idx >= 0 && next[idx].role === "assistant") {
          next[idx] = { ...next[idx], content: next[idx].content + chunk };
        }
        return next;
      });
    };

    try {
      await streamAdvisorChat(
        {
          ticker,
          question: q,
          costBasis: costBasis ? parseFloat(costBasis) : 0,
          horizonDays,
          history,
          // 首轮强制刷新数据，追问复用缓存
          useCachedContext: history.length > 0,
          signal: controller.signal,
        },
        (event: AdvisorEvent) => {
          switch (event.type) {
            case "delta":
              appendDelta(event.content);
              break;
            case "error":
              updateLast({ error: event.message, streaming: false });
              break;
            case "done":
              updateLast({ streaming: false });
              break;
            case "meta":
              // 元信息暂不展示，保留用于后续扩展（如显示引用的知识库篇数）
              break;
          }
        }
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        updateLast({ error: t("common.error.requestFailed"), streaming: false });
      }
    } finally {
      updateLast({ streaming: false });
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function handleClear() {
    setTurns([]);
    setError("");
    pinnedRef.current = true;
    setShowJumpToLatest(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Cmd/Ctrl + Enter 发送，Enter 换行
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      send(question);
    }
  }

  const notConfigured = status !== null && !status.configured;

  return (
    <div className="tab-content" ref={rootRef}>
      {notConfigured && (
        <div className="advisor-warning">{t("advisor.notConfigured")}</div>
      )}

      <div className="form-group">
        <label>{t("common.selectStock")}</label>
        <StockSearch onSelect={handleSelectTicker} value={ticker} />
        <Watchlist onSelect={handleSelectTicker} />
      </div>

      <div className="advisor-params">
        <div className="form-group">
          <label>{t("advisor.costBasis")}</label>
          <input
            type="number"
            step="0.01"
            min="0"
            className="stock-search-input"
            placeholder={t("advisor.costBasisPlaceholder")}
            value={costBasis}
            onChange={(e) => setCostBasis(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>{t("advisor.horizon")}</label>
          <select
            className="stock-search-input"
            value={horizonDays}
            onChange={(e) => setHorizonDays(parseInt(e.target.value, 10))}
          >
            <option value={7}>{t("date.1w")}</option>
            <option value={30}>{t("date.1m")}</option>
            <option value={90}>{t("date.3m")}</option>
          </select>
        </div>
      </div>

      {status?.knowledge && (
        <div className="advisor-kb-bar">
          <button
            className="advisor-kb-toggle"
            onClick={() => setShowKnowledge((v) => !v)}
          >
            {t("advisor.knowledgeBase")}: {status.knowledge.doc_count} {t("advisor.docs")}
            <span className="advisor-kb-arrow">{showKnowledge ? "\u25B2" : "\u25BC"}</span>
          </button>
          {showKnowledge && (
            <div className="advisor-kb-list">
              {status.knowledge.doc_count === 0 ? (
                <div className="advisor-kb-empty">{t("advisor.knowledgeEmpty")}</div>
              ) : (
                status.knowledge.docs.map((d) => (
                  <div key={d.path} className="advisor-kb-item">
                    <span className="advisor-kb-title">{d.title}</span>
                    <span className="advisor-kb-path">{d.path}</span>
                    <span className="advisor-kb-chars">{d.chars.toLocaleString()}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {turns.length === 0 && (
        <div className="advisor-presets">
          <div className="advisor-presets-label">{t("advisor.presetsLabel")}</div>
          <div className="advisor-presets-grid">
            {PRESET_KEYS.map((key) => (
              <button
                key={key}
                className="advisor-preset-btn"
                disabled={!ticker || streaming}
                onClick={() => send(t(key))}
              >
                {t(key)}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {turns.length > 0 && (
        <div className="advisor-chat">
          {turns.map((turn, i) => (
            <MessageBubble key={i} turn={turn} />
          ))}
        </div>
      )}

      <div className="advisor-input-area">
        {/* 绝对定位于输入区上方：不参与文档流，因此显隐不会改变 scrollHeight，
            避免"按钮出现→布局变化→贴底判定翻转→按钮消失"的自激闪烁 */}
        {showJumpToLatest && turns.length > 0 && (
          <button className="advisor-jump-latest" onClick={handleJumpToLatest}>
            {t("advisor.jumpToLatest")} ↓
          </button>
        )}
        <textarea
          className="advisor-textarea"
          rows={3}
          placeholder={t("advisor.inputPlaceholder")}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <div className="advisor-actions">
          {turns.length > 0 && (
            <button className="btn-secondary" onClick={handleClear} disabled={streaming}>
              {t("advisor.clear")}
            </button>
          )}
          {streaming ? (
            <button className="btn-secondary" onClick={handleStop}>
              {t("advisor.stop")}
            </button>
          ) : (
            <button
              className="btn"
              onClick={() => send(question)}
              disabled={!ticker || !question.trim()}
            >
              {t("advisor.send")}
            </button>
          )}
        </div>
        <div className="advisor-hint">{t("advisor.sendHint")}</div>
      </div>
    </div>
  );
}
