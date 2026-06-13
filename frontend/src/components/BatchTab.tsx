import { useEffect, useRef, useState } from "react";
import {
  BatchPredictResult,
  BatchResultItem,
  getStocks,
  predictBatch,
  searchStocks,
  Stock,
} from "../api/predict";
import { useI18n } from "../i18n/context";

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
  const { t } = useI18n();

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
            {t("batch.clear")}
          </button>
        </div>
      )}

      <input
        ref={inputRef}
        type="text"
        className="stock-search-input"
        value={query}
        placeholder={`${t("batch.searchPlaceholder")}（${t("batch.selected")} ${selected.size} ${t("batch.unit")}）`}
        autoComplete="off"
        onChange={(e) => handleInput(e.target.value)}
        onFocus={handleFocus}
        onKeyDown={handleKey}
      />

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
              {t("batch.noMatch")}
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
  const { t } = useI18n();

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
      setError(t("batch.error.selectAtLeast"));
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const tickers = Array.from(selected.keys()).join(",");
      const data = await predictBatch(tickers, targetDate);
      if (!data.success) {
        setError(data.error || t("common.error.predictFailed"));
        return;
      }
      setResult(data);
    } catch {
      setError(t("common.error.requestFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tab-content">
      <div className="form-group">
        <label>{t("batch.selectStocks")}</label>
        <MultiStockSelect
          selected={selected}
          onToggle={toggleStock}
          onClear={clearAll}
        />
      </div>

      <div className="form-group">
        <label>{t("common.targetDate")}</label>
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
        {loading ? t("common.loading") : t("batch.startPredict")}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{t("batch.analyzing")}</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <BatchResult data={result} />}
    </div>
  );
}

function BatchResult({ data }: { data: BatchPredictResult }) {
  const { t } = useI18n();

  return (
    <div style={{ marginTop: "20px" }}>
      {data.chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${data.chart}`} alt="batch chart" style={{ width: "100%" }} />
        </div>
      )}

      <div className="result-card">
        <h4>{t("batch.result.title")}</h4>
        <div className="batch-table-wrapper">
          <table className="batch-table">
            <thead>
              <tr>
                <th>{t("batch.table.stock")}</th>
                <th>{t("batch.table.currentPrice")}</th>
                <th>{t("batch.table.gbmPredict")}</th>
                <th>{t("batch.table.gbmReturn")}</th>
                <th>{t("batch.table.mcPredict")}</th>
                <th>{t("batch.table.mcReturn")}</th>
                <th>{t("batch.table.volatility")}</th>
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
