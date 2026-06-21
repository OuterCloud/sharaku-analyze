import { useEffect, useRef, useState } from "react";
import { analyzeWheel, WheelResult } from "../api/predict";
import { useI18n } from "../i18n/context";
import StockSearch from "./StockSearch";
import Watchlist from "./Watchlist";

function statusColor(status: string): string {
  switch (status) {
    case "great":
      return "#27ae60";
    case "acceptable":
    case "moderate":
    case "caution":
      return "#f39c12";
    case "danger":
    case "wait":
    case "hold":
    case "underwater":
      return "#e74c3c";
    default:
      return "#666";
  }
}

function statusIcon(status: string): string {
  switch (status) {
    case "great":
      return "\u{1F7E2}";
    case "acceptable":
    case "moderate":
    case "caution":
      return "\u{1F7E1}";
    default:
      return "\u{1F534}";
  }
}

function WheelResultView({ result }: { result: WheelResult }) {
  const { t } = useI18n();

  return (
    <div style={{ marginTop: "20px" }}>
      <div className="result-card">
        <h3 className="result-title">{result.ticker} {t("wheel.overview")}</h3>
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">{t("wheel.currentPrice")}</div>
            <div className="stat-value">${result.current_price.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.ema20")}</div>
            <div className="stat-value">${result.ema_20.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.emaDeviation")}</div>
            <div className={`stat-value ${result.ema_deviation >= 0 ? "positive" : "negative"}`}>
              {result.ema_deviation >= 0 ? "+" : ""}{result.ema_deviation.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.emaTrend")}</div>
            <div className={`stat-value ${result.ema_trend >= 0 ? "positive" : "negative"}`}>
              {result.ema_trend >= 0 ? "+" : ""}{result.ema_trend.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.volatility")}</div>
            <div className="stat-value">{result.volatility.toFixed(2)}%</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.intraDrop")}</div>
            <div className={`stat-value ${result.intra_drop >= 0 ? "positive" : "negative"}`}>
              {result.intra_drop.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("wheel.gapChange")}</div>
            <div className={`stat-value ${result.gap_and_change >= 0 ? "positive" : "negative"}`}>
              {result.gap_and_change >= 0 ? "+" : ""}{result.gap_and_change.toFixed(2)}%
            </div>
          </div>
          {result.is_v_shape && (
            <div className="stat-item">
              <div className="stat-label">{t("wheel.shape")}</div>
              <div className="stat-value positive">{t("wheel.vShape")}</div>
            </div>
          )}
        </div>
      </div>

      <div className="result-card">
        <h3 className="result-title">{t("wheel.sellPut")}</h3>
        <div className="wheel-decision" style={{ borderLeft: `4px solid ${statusColor(result.sell_put.status)}`, paddingLeft: "16px", marginBottom: "16px" }}>
          <div style={{ fontSize: "1.1em", fontWeight: 600, marginBottom: "8px" }}>
            {statusIcon(result.sell_put.status)} {result.sell_put.label}
          </div>
          <div style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}>
            {result.sell_put.reason}
          </div>
        </div>
        {result.sell_put.recommended_strike && (
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">{t("wheel.sellPut.strike")}</div>
              <div className="stat-value">${result.sell_put.recommended_strike}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">{t("wheel.sellPut.distance")}</div>
              <div className="stat-value negative">
                {result.sell_put.strike_distance_pct!.toFixed(1)}%
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">{t("wheel.sellPut.cash")}</div>
              <div className="stat-value">${result.sell_put.cash_required!.toLocaleString()}</div>
            </div>
          </div>
        )}
        <div style={{ marginTop: "12px", fontSize: "0.85em", color: "var(--text-muted)" }}>
          {t("wheel.sellPut.note")}
        </div>
      </div>

      <div className="result-card">
        <h3 className="result-title">{t("wheel.coveredCall")}</h3>
        <div style={{ fontSize: "0.9em", color: "var(--text-secondary)", marginBottom: "12px" }}>
          {t("wheel.coveredCall.cost")}: ${result.covered_call.cost_basis!.toFixed(2)}
        </div>
        <div className="wheel-decision" style={{ borderLeft: `4px solid ${statusColor(result.covered_call.status)}`, paddingLeft: "16px", marginBottom: "16px" }}>
          <div style={{ fontSize: "1.1em", fontWeight: 600, marginBottom: "8px" }}>
            {statusIcon(result.covered_call.status)} {result.covered_call.label}
          </div>
          <div style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}>
            {result.covered_call.reason}
          </div>
        </div>
        {result.covered_call.recommended_strike && (
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">{t("wheel.coveredCall.strike")}</div>
              <div className="stat-value">${result.covered_call.recommended_strike}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">{t("wheel.coveredCall.distance")}</div>
              <div className="stat-value positive">
                +{result.covered_call.strike_distance_pct!.toFixed(1)}%
              </div>
            </div>
          </div>
        )}
        {result.covered_call.recommended_strike && (
          <div style={{ marginTop: "12px", fontSize: "0.85em", color: "var(--text-muted)" }}>
            {t("wheel.coveredCall.note")}
          </div>
        )}
      </div>
    </div>
  );
}

export default function WheelTab() {
  const [ticker, setTicker] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<WheelResult | null>(null);
  const { lang, t } = useI18n();
  const prevLang = useRef(lang);

  function handleSelect(tk: string) {
    setTicker(tk);
    setResult(null);
    setError("");
  }

  // Re-fetch when language changes and we already have results
  useEffect(() => {
    if (prevLang.current !== lang && ticker && result && costBasis) {
      prevLang.current = lang;
      const cost = parseFloat(costBasis);
      if (cost > 0) {
        doAnalyze(ticker, cost, lang);
      }
    } else {
      prevLang.current = lang;
    }
  }, [lang]);

  async function doAnalyze(tk: string, cost: number, l: string) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeWheel(tk, cost, l);
      if (!data.success) {
        setError(data.error || t("common.error.analyzeFailed"));
        return;
      }
      setResult(data);
    } catch {
      setError(t("common.error.requestFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyze() {
    if (!ticker) {
      setError(t("common.error.selectStock"));
      return;
    }
    const cost = parseFloat(costBasis);
    if (!cost || cost <= 0) {
      setError(t("wheel.error.costBasis"));
      return;
    }
    doAnalyze(ticker, cost, lang);
  }

  return (
    <div className="tab-content">
      <div className="form-group">
        <label>{t("common.selectStock")}</label>
        <StockSearch onSelect={handleSelect} value={ticker} />
        <Watchlist onSelect={handleSelect} />
      </div>

      <div className="form-group">
        <label>{t("wheel.costBasis")}</label>
        <input
          type="number"
          step="0.01"
          min="0"
          placeholder={t("wheel.costPlaceholder")}
          value={costBasis}
          onChange={(e) => setCostBasis(e.target.value)}
          className="stock-search-input"
        />
      </div>

      <div className="sticky-action-bar">
        <button
          className={`btn${loading ? " loading" : ""}`}
          disabled={loading}
          onClick={handleAnalyze}
        >
          {loading ? t("common.loading") : t("wheel.startAnalyze")}
        </button>
      </div>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{t("wheel.analyzing")}</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <WheelResultView result={result} />}
    </div>
  );
}
