import { useEffect, useRef, useState } from "react";
import { getStocks, searchStocks, Stock } from "../api/predict";
import { useI18n } from "../i18n/context";

interface Props {
  onSelect: (ticker: string) => void;
  value?: string;
}

export default function StockSearch({ onSelect, value }: Props) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Stock[]>([]);
  const [show, setShow] = useState(false);
  const [focus, setFocus] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();

  useEffect(() => {
    function onClickOut(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node))
        setShow(false);
    }
    document.addEventListener("click", onClickOut);
    return () => document.removeEventListener("click", onClickOut);
  }, []);

  useEffect(() => {
    if (value && value !== query) {
      setQuery(value);
    }
  }, [value]);

  async function doSearch(val: string) {
    const stocks = val.trim() ? await searchStocks(val) : await getStocks();
    setItems(stocks);
    setShow(true);
    setFocus(-1);
  }

  function handleInput(val: string) {
    setQuery(val);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => doSearch(val), 200);
  }

  function handleFocus() {
    doSearch(query);
  }

  function select(stock: Stock) {
    setQuery(`${stock.ticker} - ${stock.name}`);
    setShow(false);
    onSelect(stock.ticker);
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
      if (focus >= 0) select(items[focus]);
    } else if (e.key === "Escape") setShow(false);
  }

  function handleClear() {
    setQuery("");
    setItems([]);
    setShow(false);
    onSelect("");
  }

  return (
    <div className="stock-search-wrapper" ref={wrapRef}>
      <div className="stock-search-input-wrap">
        <input
          type="text"
          className="stock-search-input"
          value={query}
          placeholder={t("search.placeholder")}
          autoComplete="off"
          onChange={(e) => handleInput(e.target.value)}
          onFocus={handleFocus}
          onKeyDown={handleKey}
        />
        {query && (
          <button
            className="stock-search-clear"
            onClick={handleClear}
            type="button"
            aria-label={t("search.clear")}
          >
            &times;
          </button>
        )}
      </div>
      {show && (
        <div className="stock-dropdown show">
          {items.map((s, i) => (
            <div
              key={s.ticker}
              className={`stock-dropdown-item${i === focus ? " focused" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                select(s);
              }}
            >
              <span className={`stock-market-tag ${(s.stock_type || "US").toLowerCase()}`}>
                {s.stock_type || "US"}
              </span>
              <span className="stock-code">{s.ticker}</span>
              <span className="stock-name">{s.name}</span>
            </div>
          ))}
          {items.length === 0 && (
            <div className="stock-dropdown-item" style={{ color: "#999" }}>
              {t("search.noMatch")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
