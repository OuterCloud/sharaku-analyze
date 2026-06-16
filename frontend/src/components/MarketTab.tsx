import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getMarketMovers,
  MarketMover,
  MarketMoversResult,
  MarketSession,
  predictQuickBatch,
  QuickPredictItem,
} from "../api/predict";
import { useI18n } from "../i18n/context";

type Category = "gainers" | "losers" | "actives";

interface PredictionData {
  price: number;
  returnPct: number;
}

interface ModelPredictions {
  gbm?: PredictionData;
  mc?: PredictionData;
  prophet?: PredictionData;
}

type PredictionsMap = Record<string, { week?: ModelPredictions; month?: ModelPredictions }>;

type SortKey =
  | "price" | "change" | "change_pct" | "volume"
  | "gbm_w" | "mc_w" | "prophet_w"
  | "gbm_m" | "mc_m" | "prophet_m";

type SortDir = "asc" | "desc";

const SESSION_COLORS: Record<string, string> = {
  pre_market: "#f59e0b",
  regular: "#10b981",
  after_hours: "#8b5cf6",
  overnight: "#6b7280",
  closed: "#6b7280",
};

const BATCH_SIZE = 25;

function formatVolume(vol: number): string {
  if (!vol) return "-";
  if (vol >= 1e9) return (vol / 1e9).toFixed(2) + "B";
  if (vol >= 1e6) return (vol / 1e6).toFixed(2) + "M";
  if (vol >= 1e3) return (vol / 1e3).toFixed(1) + "K";
  return vol.toString();
}

function getTargetDate(daysAhead: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  return d.toISOString().split("T")[0];
}

export default function MarketTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState<MarketSession | null>(null);
  const [data, setData] = useState<Record<string, MarketMover[]>>({});
  const [category, setCategory] = useState<Category>("gainers");
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [predictions, setPredictions] = useState<PredictionsMap>({});
  const [predictionsLoading, setPredictionsLoading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);
  const { t, lang } = useI18n();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result: MarketMoversResult = await getMarketMovers("all");
      if (!result.success) {
        setError(result.error || t("common.error.requestFailed"));
        return;
      }
      setSession(result.session);
      setData(result.data || {});
    } catch {
      setError(t("common.error.requestFailed"));
    } finally {
      setLoading(false);
      setLastUpdate(new Date().toLocaleTimeString());
    }
  }, [t]);

  // Fetch predictions for current category movers
  const fetchPredictions = useCallback(async (movers: MarketMover[]) => {
    if (!movers.length) return;

    // Abort any in-flight prediction request
    if (abortRef.current) {
      abortRef.current.abort();
    }
    abortRef.current = new AbortController();

    setPredictionsLoading(true);
    setPredictions({});

    const tickers = movers.map((m) => m.ticker);
    const weekDate = getTargetDate(7);
    const monthDate = getTargetDate(30);

    // Process in batches of BATCH_SIZE
    for (let i = 0; i < tickers.length; i += BATCH_SIZE) {
      if (abortRef.current.signal.aborted) return;

      const batch = tickers.slice(i, i + BATCH_SIZE);

      // Fetch week and month predictions in parallel for this batch
      const [weekRes, monthRes] = await Promise.allSettled([
        predictQuickBatch(batch, weekDate),
        predictQuickBatch(batch, monthDate),
      ]);

      if (abortRef.current.signal.aborted) return;

      setPredictions((prev) => {
        const next = { ...prev };

        if (weekRes.status === "fulfilled" && weekRes.value.success) {
          weekRes.value.results.forEach((item: QuickPredictItem) => {
            if (!next[item.ticker]) next[item.ticker] = {};
            next[item.ticker].week = {
              gbm: { price: item.gbm_mean_price, returnPct: item.gbm_return },
              mc: { price: item.mc_mean_price, returnPct: item.mc_return },
              prophet: item.prophet_mean_price != null && item.prophet_return != null
                ? { price: item.prophet_mean_price, returnPct: item.prophet_return }
                : undefined,
            };
          });
        }

        if (monthRes.status === "fulfilled" && monthRes.value.success) {
          monthRes.value.results.forEach((item: QuickPredictItem) => {
            if (!next[item.ticker]) next[item.ticker] = {};
            next[item.ticker].month = {
              gbm: { price: item.gbm_mean_price, returnPct: item.gbm_return },
              mc: { price: item.mc_mean_price, returnPct: item.mc_return },
              prophet: item.prophet_mean_price != null && item.prophet_return != null
                ? { price: item.prophet_mean_price, returnPct: item.prophet_return }
                : undefined,
            };
          });
        }

        return next;
      });
    }

    setPredictionsLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, 60000);
    return () => clearInterval(timerRef.current);
  }, [fetchData]);

  // Trigger predictions when movers change
  const movers = data[category] || [];

  useEffect(() => {
    if (movers.length > 0) {
      fetchPredictions(movers);
    }
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [category, movers.length > 0 ? movers.map(m => m.ticker).join(",") : "", fetchPredictions]);

  // Reset sort when category changes
  useEffect(() => {
    setSortKey(null);
  }, [category]);

  // Sort logic
  const getPredReturn = (ticker: string, period: "week" | "month", model: "gbm" | "mc" | "prophet"): number | null => {
    return predictions[ticker]?.[period]?.[model]?.returnPct ?? null;
  };

  const sortedMovers = useMemo(() => {
    if (!sortKey) return movers;

    const sorted = [...movers];
    sorted.sort((a, b) => {
      let va: number | null = null;
      let vb: number | null = null;

      switch (sortKey) {
        case "price": va = a.price; vb = b.price; break;
        case "change": va = a.change; vb = b.change; break;
        case "change_pct": va = a.change_pct; vb = b.change_pct; break;
        case "volume": va = a.volume; vb = b.volume; break;
        case "gbm_w": va = getPredReturn(a.ticker, "week", "gbm"); vb = getPredReturn(b.ticker, "week", "gbm"); break;
        case "mc_w": va = getPredReturn(a.ticker, "week", "mc"); vb = getPredReturn(b.ticker, "week", "mc"); break;
        case "prophet_w": va = getPredReturn(a.ticker, "week", "prophet"); vb = getPredReturn(b.ticker, "week", "prophet"); break;
        case "gbm_m": va = getPredReturn(a.ticker, "month", "gbm"); vb = getPredReturn(b.ticker, "month", "gbm"); break;
        case "mc_m": va = getPredReturn(a.ticker, "month", "mc"); vb = getPredReturn(b.ticker, "month", "mc"); break;
        case "prophet_m": va = getPredReturn(a.ticker, "month", "prophet"); vb = getPredReturn(b.ticker, "month", "prophet"); break;
      }

      // Nulls go to bottom
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;

      return sortDir === "desc" ? vb - va : va - vb;
    });
    return sorted;
  }, [movers, sortKey, sortDir, predictions]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return <span className="sort-icon">⇅</span>;
    return <span className="sort-icon active">{sortDir === "desc" ? "↓" : "↑"}</span>;
  };

  const sessionLabel = session
    ? lang === "zh" ? session.label_zh : session.label_en
    : "";
  const sessionColor = session ? SESSION_COLORS[session.session] || "#6b7280" : "#6b7280";

  const renderPredictCell = (ticker: string, period: "week" | "month", model: "gbm" | "mc" | "prophet") => {
    const modelPred = predictions[ticker]?.[period]?.[model];
    if (modelPred) {
      const color = modelPred.returnPct >= 0 ? "var(--positive)" : "var(--negative)";
      const sign = modelPred.returnPct >= 0 ? "+" : "";
      return (
        <td className="predict-cell">
          <span className="predict-price">${modelPred.price.toFixed(2)}</span>
          <br />
          <span className="predict-return" style={{ color }}>
            {sign}{(modelPred.returnPct * 100).toFixed(1)}%
          </span>
        </td>
      );
    }
    // If we have predictions for this ticker but this model is missing (Prophet failed)
    if (predictions[ticker]?.[period] && model === "prophet") {
      return <td className="predict-cell predict-na">-</td>;
    }
    if (predictionsLoading) {
      return (
        <td><span className="skeleton-cell" /></td>
      );
    }
    return <td className="predict-cell predict-na">-</td>;
  };

  return (
    <div className="tab-content">
      {/* Session Status Bar - only show when data is loaded */}
      {session && (
        <div className="market-session-bar">
          <div className="market-session-info">
            <span
              className="market-session-dot"
              style={{ backgroundColor: sessionColor }}
            />
            <span className="market-session-label" style={{ color: sessionColor }}>
              {sessionLabel}
            </span>
            <span className="market-session-time">
              ET {session.eastern_time}
            </span>
            {(session.session === "overnight" || session.session === "closed") && (
              <span className="market-delayed-hint">
                {t("market.closedNotice")}
              </span>
            )}
          </div>
          <div className="market-session-actions">
            {lastUpdate && (
              <span className="market-last-update">
                {t("market.lastUpdate")}: {lastUpdate}
              </span>
            )}
            <button
              className={`btn-refresh${loading ? " spinning" : ""}`}
              onClick={fetchData}
              disabled={loading}
              title={t("market.refresh")}
            >
              &#x21bb;
            </button>
          </div>
        </div>
      )}

      {/* Category Tabs */}
      <div className="market-categories">
        <button
          className={`market-cat-btn${category === "gainers" ? " active gainers" : ""}`}
          onClick={() => setCategory("gainers")}
        >
          {t("market.cat.gainers")}
        </button>
        <button
          className={`market-cat-btn${category === "losers" ? " active losers" : ""}`}
          onClick={() => setCategory("losers")}
        >
          {t("market.cat.losers")}
        </button>
        <button
          className={`market-cat-btn${category === "actives" ? " active actives" : ""}`}
          onClick={() => setCategory("actives")}
        >
          {t("market.cat.actives")}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading && movers.length === 0 && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{t("market.loading")}</p>
        </div>
      )}

      {movers.length > 0 && (
        <div className="result-card">
          <div className="market-table-header">
            <h4>
              {t(`market.cat.${category}` as any)}
              <small style={{ color: "#888", fontWeight: "normal", marginLeft: 8 }}>
                ({lang === "zh" ? movers[0]?.ref_label_zh : movers[0]?.ref_label_en})
              </small>
            </h4>
            <span className="market-count">
              {movers.length} {t("market.stocks")}
              {predictionsLoading && (
                <small style={{ marginLeft: 8, color: "var(--text-muted)" }}>
                  {t("market.predicting")}
                </small>
              )}
            </span>
          </div>

          <div className="batch-table-wrapper">
            <table className="batch-table market-table market-table-6col">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("market.table.stock")}</th>
                  <th className="sortable" onClick={() => handleSort("price")}>
                    {t("market.table.price")} {sortIndicator("price")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("change")}>
                    {t("market.table.change")} {sortIndicator("change")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("change_pct")}>
                    {t("market.table.changePct")} {sortIndicator("change_pct")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("volume")}>
                    {t("market.table.volume")} {sortIndicator("volume")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("gbm_w")}>
                    {t("market.table.gbm1W")} {sortIndicator("gbm_w")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("mc_w")}>
                    {t("market.table.mc1W")} {sortIndicator("mc_w")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("prophet_w")}>
                    {t("market.table.prophet1W")} {sortIndicator("prophet_w")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("gbm_m")}>
                    {t("market.table.gbm1M")} {sortIndicator("gbm_m")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("mc_m")}>
                    {t("market.table.mc1M")} {sortIndicator("mc_m")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("prophet_m")}>
                    {t("market.table.prophet1M")} {sortIndicator("prophet_m")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedMovers.map((m, idx) => (
                  <tr key={m.ticker}>
                    <td className="market-rank">{idx + 1}</td>
                    <td>
                      <strong>{m.ticker}</strong>
                      <br />
                      <small>{m.name}</small>
                    </td>
                    <td>${m.price.toFixed(2)}</td>
                    <td className={m.change >= 0 ? "positive" : "negative"}>
                      {m.change >= 0 ? "+" : ""}
                      {m.change.toFixed(2)}
                    </td>
                    <td className={m.change_pct >= 0 ? "positive" : "negative"}>
                      <strong>
                        {m.change_pct >= 0 ? "+" : ""}
                        {m.change_pct.toFixed(2)}%
                      </strong>
                    </td>
                    <td>{formatVolume(m.volume)}</td>
                    {renderPredictCell(m.ticker, "week", "gbm")}
                    {renderPredictCell(m.ticker, "week", "mc")}
                    {renderPredictCell(m.ticker, "week", "prophet")}
                    {renderPredictCell(m.ticker, "month", "gbm")}
                    {renderPredictCell(m.ticker, "month", "mc")}
                    {renderPredictCell(m.ticker, "month", "prophet")}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && movers.length === 0 && !error && (
        <div className="market-empty">
          {t("market.empty")}
        </div>
      )}
    </div>
  );
}
