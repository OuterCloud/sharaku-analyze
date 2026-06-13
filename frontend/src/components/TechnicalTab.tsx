import { useState } from "react";
import { analyzeTechnical, TechnicalResult } from "../api/predict";
import StockSearch from "./StockSearch";

function signalColor(signal: string): string {
  if (signal.startsWith("看多") || signal.startsWith("偏多")) return "#27ae60";
  if (signal.startsWith("看空") || signal.startsWith("偏空")) return "#e74c3c";
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
  if (advice.startsWith("看多")) return "#27ae60";
  if (advice.startsWith("偏多")) return "#66bb6a";
  if (advice.startsWith("看空")) return "#e74c3c";
  if (advice.startsWith("偏空")) return "#ef5350";
  return "#ff9800";
}

function TechnicalResultView({ result }: { result: TechnicalResult }) {
  const signalEntries = Object.entries(result.signals);

  return (
    <div style={{ marginTop: "20px" }}>
      {/* Score */}
      <div className="result-card">
        <h3 className="result-title">
          {result.ticker} 综合评分
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
            <span>看空 0</span>
            <span>中性 50</span>
            <span>看多 100</span>
          </div>
        </div>
        <div className="stat-item" style={{ marginTop: "12px" }}>
          <div className="stat-label">当前价格</div>
          <div className="stat-value">${result.current_price.toFixed(2)}</div>
        </div>
      </div>

      {/* Signals Grid */}
      <div className="result-card">
        <h3 className="result-title">指标信号</h3>
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

      {/* Candlestick Pattern */}
      {result.candlestick_pattern && (
        <div className="result-card">
          <h3 className="result-title">K线形态识别</h3>
          <div
            className="ta-pattern-card"
            style={{ borderLeftColor: signalColor(result.candlestick_pattern.signal) }}
          >
            <div className="ta-pattern-name">{result.candlestick_pattern.name}</div>
            <div className="ta-pattern-desc">{result.candlestick_pattern.description}</div>
          </div>
        </div>
      )}

      {/* Price Targets */}
      {result.stop_loss !== undefined && result.target !== undefined && (
        <div className="result-card">
          <h3 className="result-title">价格目标</h3>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">止损位</div>
              <div className="stat-value negative">
                ${result.stop_loss.toFixed(2)}
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">目标位</div>
              <div className="stat-value positive">
                ${result.target.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Advice */}
      <div className="result-card">
        <h3 className="result-title">综合建议</h3>
        <div
          className="ta-advice-card"
          style={{ borderLeftColor: adviceColor(result.advice) }}
        >
          {result.advice}
        </div>
      </div>

      {/* Warning */}
      <div className="ta-warning">{result.warning}</div>
    </div>
  );
}

export default function TechnicalTab() {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TechnicalResult | null>(null);

  function handleSelect(t: string) {
    setTicker(t);
    setResult(null);
    setError("");
  }

  async function handleAnalyze() {
    if (!ticker) {
      setError("请先选择股票");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeTechnical(ticker);
      if (!data.success) {
        setError(data.error || "分析失败");
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
        <label>选择股票</label>
        <StockSearch onSelect={handleSelect} />
      </div>

      <button
        className={`btn${loading ? " loading" : ""}`}
        disabled={loading}
        onClick={handleAnalyze}
      >
        {loading ? "分析中..." : "开始分析"}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>正在计算技术指标...</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <TechnicalResultView result={result} />}
    </div>
  );
}
