import { useEffect, useRef, useState } from "react";
import {
  BatchPredictResult,
  BatchResultItem,
  getStocks,
  predictBatch,
  searchStocks,
  Stock,
} from "../api/predict";

interface Props {
  defaultDate: string;
}

function MultiStockSelect({
  selected,
  onToggle,
  onClear,
}: {
  selected: Map<string, string>;
  onToggle: (stock: Stock) => void;
  onClear: () => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Stock[]>([]);
  const [show, setShow] = useState(false);
  const [focus, setFocus] = useState(-1);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    function onClickOut(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node))
        setShow(false);
    }
    document.addEventListener("click", onClickOut);
    return () => document.removeEventListener("click", onClickOut);
  }, []);

  async function loadStocks(q: string) {
    const stocks = q.trim() ? await searchStocks(q) : await getStocks();
    setItems(stocks);
    setShow(true);
    setFocus(-1);
  }

  function handleInput(val: string) {
    setQuery(val);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => loadStocks(val), 200);
  }

  function handleFocus() {
    loadStocks(query);
  }

  function handleKey(e: React.KeyboardEvent) {
    if (!show) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocus((f) => Math.min(f + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocus((f) => Math.max(f - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (focus >= 0) onToggle(items[focus]);
    } else if (e.key === "Escape") {
      setShow(false);
    }
  }

  return (
    <div className="multi-select-wrapper" ref={wrapRef}>
      {/* 已选标签 */}
      {selected.size > 0 && (
        <div className="multi-select-tags">
          {Array.from(selected.entries()).map(([ticker, name]) => (
            <span key={ticker} className="multi-select-tag">
              <strong>{ticker}</strong>
              <button
                className="multi-select-tag-remove"
                onClick={() => onToggle({ ticker, name, stock_type: "US" })}
              >
                &times;
              </button>
            </span>
          ))}
          <button className="multi-select-clear" onClick={onClear}>
            清空
          </button>
        </div>
      )}

      {/* 搜索输入 */}
      <input
        ref={inputRef}
        type="text"
        className="stock-search-input"
        value={query}
        placeholder={`搜索添加股票...（已选 ${selected.size} 只）`}
        autoComplete="off"
        onChange={(e) => handleInput(e.target.value)}
        onFocus={handleFocus}
        onKeyDown={handleKey}
      />

      {/* 下拉列表 */}
      {show && (
        <div className="stock-dropdown show">
          {items.map((s, i) => {
            const isSelected = selected.has(s.ticker);
            return (
              <div
                key={s.ticker}
                className={`stock-dropdown-item${i === focus ? " focused" : ""}${isSelected ? " selected" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onToggle(s);
                }}
              >
                <span className="multi-select-check">
                  {isSelected ? "\u2611" : "\u2610"}
                </span>
                <span className={`stock-market-tag ${(s.stock_type || "US").toLowerCase()}`}>
                  {s.stock_type || "US"}
                </span>
                <span className="stock-code">{s.ticker}</span>
                <span className="stock-name">{s.name}</span>
              </div>
            );
          })}
          {items.length === 0 && (
            <div className="stock-dropdown-item" style={{ color: "#999" }}>
              无匹配结果
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BatchTab({ defaultDate }: Props) {
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const [targetDate, setTargetDate] = useState(defaultDate);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BatchPredictResult | null>(null);

  function toggleStock(stock: Stock) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(stock.ticker)) {
        next.delete(stock.ticker);
      } else {
        next.set(stock.ticker, stock.name);
      }
      return next;
    });
  }

  function clearAll() {
    setSelected(new Map());
  }

  async function handlePredict() {
    if (selected.size === 0) {
      setError("请至少选择一只股票");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const tickers = Array.from(selected.keys()).join(",");
      const data = await predictBatch(tickers, targetDate);
      if (!data.success) {
        setError(data.error || "预测失败");
        return;
      }
      setResult(data);
    } catch {
      setError("请求失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tab-content">
      <div className="form-group">
        <label>选择股票（可多选）</label>
        <MultiStockSelect
          selected={selected}
          onToggle={toggleStock}
          onClear={clearAll}
        />
      </div>

      <div className="form-group">
        <label>预测目标日期</label>
        <input
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
        />
      </div>

      <button
        className={`btn${loading ? " loading" : ""}`}
        disabled={loading}
        onClick={handlePredict}
      >
        {loading ? "分析中..." : "批量预测"}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>正在批量分析中，请稍候...</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <BatchResult data={result} />}
    </div>
  );
}

function BatchResult({ data }: { data: BatchPredictResult }) {
  return (
    <div style={{ marginTop: "20px" }}>
      {data.chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${data.chart}`} alt="批量对比图" style={{ width: "100%" }} />
        </div>
      )}

      <div className="result-card">
        <h4>预测结果排名（按预期收益率）</h4>
        <div className="batch-table-wrapper">
          <table className="batch-table">
            <thead>
              <tr>
                <th>股票</th>
                <th>当前价格</th>
                <th>GBM预测</th>
                <th>GBM收益</th>
                <th>MC预测</th>
                <th>MC收益</th>
                <th>波动率</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r: BatchResultItem) => (
                <tr key={r.ticker}>
                  <td>
                    <strong>{r.ticker}</strong>
                    <br />
                    <small>{r.name}</small>
                  </td>
                  <td>${r.current_price.toFixed(2)}</td>
                  <td>${r.gbm_mean_price.toFixed(2)}</td>
                  <td className={r.gbm_return >= 0 ? "positive" : "negative"}>
                    {r.gbm_return.toFixed(2)}%
                  </td>
                  <td>${r.mc_mean_price.toFixed(2)}</td>
                  <td className={r.mc_return >= 0 ? "positive" : "negative"}>
                    {r.mc_return.toFixed(2)}%
                  </td>
                  <td>{(r.volatility * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
