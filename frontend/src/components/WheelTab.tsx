import { useState } from "react";
import { analyzeWheel, WheelResult } from "../api/predict";
import StockSearch from "./StockSearch";

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
  return (
    <div style={{ marginTop: "20px" }}>
      {/* 市场概况 */}
      <div className="result-card">
        <h3 className="result-title">{result.ticker} 盘面概况</h3>
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">当前价格</div>
            <div className="stat-value">${result.current_price.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">20日EMA</div>
            <div className="stat-value">${result.ema_20.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">相对EMA偏离</div>
            <div className={`stat-value ${result.ema_deviation >= 0 ? "positive" : "negative"}`}>
              {result.ema_deviation >= 0 ? "+" : ""}{result.ema_deviation.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">EMA趋势(5日)</div>
            <div className={`stat-value ${result.ema_trend >= 0 ? "positive" : "negative"}`}>
              {result.ema_trend >= 0 ? "+" : ""}{result.ema_trend.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">年化波动率</div>
            <div className="stat-value">{result.volatility.toFixed(2)}%</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">日内最大下探</div>
            <div className={`stat-value ${result.intra_drop >= 0 ? "positive" : "negative"}`}>
              {result.intra_drop.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">隔夜+盘中涨幅</div>
            <div className={`stat-value ${result.gap_and_change >= 0 ? "positive" : "negative"}`}>
              {result.gap_and_change >= 0 ? "+" : ""}{result.gap_and_change.toFixed(2)}%
            </div>
          </div>
          {result.is_v_shape && (
            <div className="stat-item">
              <div className="stat-label">形态</div>
              <div className="stat-value positive">V型反转</div>
            </div>
          )}
        </div>
      </div>

      {/* Sell Put 决策 */}
      <div className="result-card">
        <h3 className="result-title">Sell Put 决策</h3>
        <div className="wheel-decision" style={{ borderLeft: `4px solid ${statusColor(result.sell_put.status)}`, paddingLeft: "16px", marginBottom: "16px" }}>
          <div style={{ fontSize: "1.1em", fontWeight: 600, marginBottom: "8px" }}>
            {statusIcon(result.sell_put.status)} {result.sell_put.label}
          </div>
          <div style={{ color: "#555", lineHeight: 1.6 }}>
            {result.sell_put.reason}
          </div>
        </div>
        {result.sell_put.recommended_strike && (
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">推荐行权价</div>
              <div className="stat-value">${result.sell_put.recommended_strike}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">距当前价</div>
              <div className="stat-value negative">
                {result.sell_put.strike_distance_pct!.toFixed(1)}%
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-label">单手担保现金</div>
              <div className="stat-value">${result.sell_put.cash_required!.toLocaleString()}</div>
            </div>
          </div>
        )}
        <div style={{ marginTop: "12px", fontSize: "0.85em", color: "#888" }}>
          * 推荐下周五到期，1个标准差外的安全距离
        </div>
      </div>

      {/* Covered Call 决策 */}
      <div className="result-card">
        <h3 className="result-title">Covered Call 决策</h3>
        <div style={{ fontSize: "0.9em", color: "#666", marginBottom: "12px" }}>
          持仓成本: ${result.covered_call.cost_basis!.toFixed(2)}
        </div>
        <div className="wheel-decision" style={{ borderLeft: `4px solid ${statusColor(result.covered_call.status)}`, paddingLeft: "16px", marginBottom: "16px" }}>
          <div style={{ fontSize: "1.1em", fontWeight: 600, marginBottom: "8px" }}>
            {statusIcon(result.covered_call.status)} {result.covered_call.label}
          </div>
          <div style={{ color: "#555", lineHeight: 1.6 }}>
            {result.covered_call.reason}
          </div>
        </div>
        {result.covered_call.recommended_strike && (
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-label">推荐行权价</div>
              <div className="stat-value">${result.covered_call.recommended_strike}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label">距当前价</div>
              <div className="stat-value positive">
                +{result.covered_call.strike_distance_pct!.toFixed(1)}%
              </div>
            </div>
          </div>
        )}
        {result.covered_call.recommended_strike && (
          <div style={{ marginTop: "12px", fontSize: "0.85em", color: "#888" }}>
            * 若下周五收盘前未冲破该位置，你将躺赚100%期权费并保留正股底仓
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
    const cost = parseFloat(costBasis);
    if (!cost || cost <= 0) {
      setError("请输入有效的持仓成本价");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeWheel(ticker, cost);
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

      <div className="form-group">
        <label>正股持仓成本价 ($)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          placeholder="例如: 150.00"
          value={costBasis}
          onChange={(e) => setCostBasis(e.target.value)}
          className="stock-search-input"
        />
      </div>

      <button
        className={`btn${loading ? " loading" : ""}`}
        disabled={loading}
        onClick={handleAnalyze}
      >
        {loading ? "分析中..." : "Wheel策略分析"}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>正在获取实时数据并分析...</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <WheelResultView result={result} />}
    </div>
  );
}
