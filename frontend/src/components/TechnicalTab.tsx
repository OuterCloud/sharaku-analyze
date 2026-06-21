import { useEffect, useRef, useState } from "react";
import { analyzeTechnical, TechnicalResult } from "../api/predict";
import { useI18n } from "../i18n/context";
import StockSearch from "./StockSearch";
import Watchlist from "./Watchlist";

function signalColor(signal: string): string {
  if (signal.startsWith("看多") || signal.startsWith("偏多") || signal.startsWith("Bullish") || signal.startsWith("Slightly Bullish")) return "#27ae60";
  if (signal.startsWith("看空") || signal.startsWith("偏空") || signal.startsWith("Bearish") || signal.startsWith("Slightly Bearish")) return "#e74c3c";
  return "#888";
}

function scoreColor(score: number): string {
  if (score >= 65) return "#27ae60";
  if (score >= 55) return "#66bb6a";
  if (score <= 35) return "#e74c3c";
  if (score <= 45) return "#ef5350";
  return "#ff9800";
}

function adviceColor(advice: string): string {
  if (advice.startsWith("看多") || advice.match(/^Bullish\b/)) return "#27ae60";
  if (advice.startsWith("偏多") || advice.startsWith("Slightly Bullish")) return "#66bb6a";
  if (advice.startsWith("看空") || advice.match(/^Bearish\b/)) return "#e74c3c";
  if (advice.startsWith("偏空") || advice.startsWith("Slightly Bearish")) return "#ef5350";
  return "#ff9800";
}

function TechnicalResultView({ result }: { result: TechnicalResult }) {
  const signalEntries = Object.entries(result.signals);
  const { t } = useI18n();

  return (
    <div style={{ marginTop: "20px" }}>
      <div className="result-card">
        <h3 className="result-title">
          {result.ticker} {t("technical.score.title")}
        </h3>
        <div className="ta-score-section">
          <div className="ta-score-number" style={{ color: scoreColor(result.score) }}>
            {result.score.toFixed(1)}
          </div>
          <div className="ta-score-bar">
            <div
              className="ta-score-bar-fill"
              style={{ width: `${result.score}%` }}
            />
            <div
              className="ta-score-bar-indicator"
              style={{ left: `${result.score}%` }}
            />
          </div>
          <div className="ta-score-labels">
            <span>{t("technical.score.bearish")}</span>
            <span>{t("technical.score.neutral")}</span>
            <span>{t("technical.score.bullish")}</span>
          </div>
        </div>
        <div className="stat-item" style={{ marginTop: "12px" }}>
          <div className="stat-label">{t("wheel.currentPrice")}</div>
          <div className="stat-value">${result.current_price.toFixed(2)}</div>
        </div>
      </div>

      <div className="result-card">
        <h3 className="result-title">{t("technical.signals.title")}</h3>
        <div className="ta-signals-grid">
          {signalEntries.map(([name, signal]) => (
            <div
              key={name}
              className="ta-signal-item"
              style={{ borderLeftColor: signalColor(signal) }}
            >
              <div className="ta-signal-name">{name}</div>
              <div className="ta-signal-value" style={{ color: signalColor(signal) }}>
                {signal}
              </div>
            </div>
          ))}
        </div>
      </div>

      {result.candlestick_pattern && (
        <div className="result-card">
          <h3 className="result-title">{t("technical.pattern.title")}</h3>
          <div
            className="ta-pattern-card"
            style={{ borderLeftColor: signalColor(result.candlestick_pattern.signal) }}
          >
            <div className="ta-pattern-name">{result.candlestick_pattern.name}</div>
            <div className="ta-pattern-desc">{result.candlestick_pattern.description}</div>
          </div>
        </div>
      )}

      {result.stop_loss !== undefined && result.target !== undefined && (
        <div className="result-card">
          <h3 className="result-title">{t("technical.priceTarget.title")}</h3>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">{t("technical.priceTarget.stopLoss")}</div>
              <div className="stat-value negative">
                ${result.stop_loss.toFixed(2)}
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">{t("technical.priceTarget.target")}</div>
              <div className="stat-value positive">
                ${result.target.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="result-card">
        <h3 className="result-title">{t("technical.advice.title")}</h3>
        <div
          className="ta-advice-card"
          style={{ borderLeftColor: adviceColor(result.advice) }}
        >
          {result.advice}
        </div>
      </div>

      <div className="ta-warning">{result.warning}</div>
    </div>
  );
}

export default function TechnicalTab() {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TechnicalResult | null>(null);
  const { lang, t } = useI18n();
  const prevLang = useRef(lang);

  function handleSelect(tk: string) {
    setTicker(tk);
    setResult(null);
    setError("");
  }

  // Re-fetch when language changes and we already have results
  useEffect(() => {
    if (prevLang.current !== lang && ticker && result) {
      prevLang.current = lang;
      doAnalyze(ticker, lang);
    } else {
      prevLang.current = lang;
    }
  }, [lang]);

  async function doAnalyze(tk: string, l: string) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeTechnical(tk, l);
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
    doAnalyze(ticker, lang);
  }

  return (
    <div className="tab-content">
      <div className="form-group">
        <label>{t("common.selectStock")}</label>
        <StockSearch onSelect={handleSelect} value={ticker} />
        <Watchlist onSelect={handleSelect} />
      </div>

      <div className="sticky-action-bar">
        <button
          className={`btn${loading ? " loading" : ""}`}
          disabled={loading}
          onClick={handleAnalyze}
        >
          {loading ? t("common.loading") : t("technical.startAnalyze")}
        </button>
      </div>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{t("technical.analyzing")}</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <TechnicalResultView result={result} />}
    </div>
  );
}
