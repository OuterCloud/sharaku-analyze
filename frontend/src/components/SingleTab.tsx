import { useEffect, useRef, useState } from "react";
import { predictSingle, SinglePredictResult } from "../api/predict";
import { useI18n } from "../i18n/context";
import { copyToClipboard } from "../utils/clipboard";
import StockSearch from "./StockSearch";
import Watchlist from "./Watchlist";

interface Props {
  defaultDate: string;
  initialTicker?: string;
}

function PredictResult({ result }: { result: SinglePredictResult }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();

  function buildSummaryText(r: SinglePredictResult): string {
    const s = r.stats_summary!;
    let text = `${t("summary.stockInfo")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${t("summary.ticker")}: ${r.ticker}
${t("summary.name")}: ${r.name}
${t("summary.currentPrice")}: $${r.current_price.toFixed(2)}
${t("summary.targetDate")}: ${r.target_date}
${t("summary.tradingDays")}: ${r.trading_days} ${t("summary.days")}

${t("summary.gbm.title")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${t("summary.meanPrice")}: $${s.gbm.mean.toFixed(2)}
${t("summary.medianPrice")}: $${s.gbm.median.toFixed(2)}
${t("summary.std")}: $${s.gbm.std.toFixed(2)}
${t("summary.ci")}: $${s.gbm.percentile_5.toFixed(2)} - $${s.gbm.percentile_95.toFixed(2)}
${t("summary.expectedReturn")}: ${s.gbm.expected_return.toFixed(2)}%

${t("summary.mc.title")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${t("summary.meanPrice")}: $${s.mc.mean.toFixed(2)}
${t("summary.medianPrice")}: $${s.mc.median.toFixed(2)}
${t("summary.std")}: $${s.mc.std.toFixed(2)}
${t("summary.ci")}: $${s.mc.percentile_5.toFixed(2)} - $${s.mc.percentile_95.toFixed(2)}
${t("summary.expectedReturn")}: ${s.mc.expected_return.toFixed(2)}%`;

    if (r.prophet) {
      text += `

${t("summary.prophet.title")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${t("summary.prophet.price")}: $${r.prophet.mean_price.toFixed(2)}
${t("summary.prophet.ci")}: $${r.prophet.lower_bound.toFixed(2)} - $${r.prophet.upper_bound.toFixed(2)}
${t("summary.prophet.return")}: ${r.prophet.return.toFixed(2)}%
${t("summary.prophet.risk")}: ${t(`summary.prophet.risk.${r.prophet.risk_level}` as any)}`;
    }

    text += `

${t("summary.risk.title")}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${t("summary.risk.volatility")}: ${(r.volatility * 100).toFixed(2)}%`;

    return text;
  }

  async function handleCopy() {
    if (!result.stats_summary) return;
    try {
      await copyToClipboard(buildSummaryText(result));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert(t("single.result.copyFailed"));
    }
  }

  return (
    <div ref={contentRef}>
      <div className="result-card" style={{ marginTop: "20px" }}>
        <h3 className="result-title">{t("single.result.title")}</h3>

        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">{t("single.result.currentPrice")}</div>
            <div className="stat-value">${result.current_price.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("single.result.gbmPrice")}</div>
            <div className={`stat-value ${result.gbm.return >= 0 ? "positive" : "negative"}`}>
              ${result.gbm.mean_price.toFixed(2)}
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("single.result.mcPrice")}</div>
            <div className={`stat-value ${result.mc.return >= 0 ? "positive" : "negative"}`}>
              ${result.mc.mean_price.toFixed(2)}
            </div>
          </div>
          {result.prophet && (
            <div className="stat-item">
              <div className="stat-label">{t("single.result.prophetPrice")}</div>
              <div className={`stat-value ${result.prophet.return >= 0 ? "positive" : "negative"}`}>
                ${result.prophet.mean_price.toFixed(2)}
              </div>
            </div>
          )}
          <div className="stat-item">
            <div className="stat-label">{t("single.result.expectedReturn")}</div>
            <div className={`stat-value ${result.gbm.return >= 0 ? "positive" : "negative"}`}>
              {result.gbm.return.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("single.result.percentile5")}</div>
            <div className="stat-value">${result.gbm.percentile_5.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">{t("single.result.percentile95")}</div>
            <div className="stat-value">${result.gbm.percentile_95.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {result.stats_summary && (
        <div className="result-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h4>{t("single.result.summaryTitle")}</h4>
            <button onClick={handleCopy} className="btn-copy">
              {copied ? t("single.result.copied") : t("single.result.copy")}
            </button>
          </div>
          <pre className="summary-pre">{buildSummaryText(result)}</pre>
        </div>
      )}

      {result.chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.chart}`} alt="chart" style={{ width: "100%" }} />
        </div>
      )}
      {result.mc_paths_chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.mc_paths_chart}`} alt="mc paths" style={{ width: "100%" }} />
        </div>
      )}
      {result.mc_cumulative_returns_chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.mc_cumulative_returns_chart}`} alt="cumulative returns" style={{ width: "100%" }} />
        </div>
      )}
      {result.prophet_chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.prophet_chart}`} alt="prophet forecast" style={{ width: "100%" }} />
        </div>
      )}
    </div>
  );
}

export default function SingleTab({ defaultDate, initialTicker }: Props) {
  const [ticker, setTicker] = useState("");
  const [targetDate, setTargetDate] = useState(defaultDate);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SinglePredictResult | null>(null);
  const { t } = useI18n();

  useEffect(() => {
    if (initialTicker && initialTicker !== ticker) {
      setTicker(initialTicker);
      setResult(null);
      setError("");
    }
  }, [initialTicker]);

  function handleSelect(tk: string) {
    setTicker(tk);
    setResult(null);
    setError("");
  }

  async function handlePredict() {
    if (!ticker) {
      setError(t("common.error.selectStock"));
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await predictSingle(ticker, targetDate);
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
        <label>{t("common.selectStock")}</label>
        <StockSearch onSelect={handleSelect} value={ticker} />
        <Watchlist onSelect={handleSelect} />
      </div>

      <div className="form-group">
        <label>{t("common.targetDate")}</label>
        <input
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
        />
        <div className="date-quick-picks">
          {[
            { label: t("date.1w"), days: 7 },
            { label: t("date.1m"), days: 30 },
            { label: t("date.3m"), days: 90 },
          ].map(({ label, days }) => (
            <button
              key={days}
              type="button"
              className="date-quick-btn"
              onClick={() => {
                const d = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
                setTargetDate(d.toISOString().slice(0, 10));
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="sticky-action-bar">
        <button
          className={`btn${loading ? " loading" : ""}`}
          disabled={loading}
          onClick={handlePredict}
        >
          {loading ? t("common.loading") : t("single.startPredict")}
        </button>
      </div>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{t("single.analyzing")}</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <PredictResult result={result} />}
    </div>
  );
}
