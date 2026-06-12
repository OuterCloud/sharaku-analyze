import { useRef, useState } from "react";
import { predictSingle, SinglePredictResult } from "../api/predict";
import { copyToClipboard } from "../utils/clipboard";
import StockSearch from "./StockSearch";

interface Props {
  defaultDate: string;
}

function buildSummaryText(result: SinglePredictResult): string {
  const s = result.stats_summary!;
  let text = `股票信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
股票代码: ${result.ticker}
公司名称: ${result.name}
当前价格: $${result.current_price.toFixed(2)}
预测目标日期: ${result.target_date}
预测天数: ${result.trading_days} 天

[GBM] 几何布朗运动模型结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
均值价格: $${s.gbm.mean.toFixed(2)}
中位数价格: $${s.gbm.median.toFixed(2)}
标准差: $${s.gbm.std.toFixed(2)}
5%-95%置信区间: $${s.gbm.percentile_5.toFixed(2)} - $${s.gbm.percentile_95.toFixed(2)}
预期收益率: ${s.gbm.expected_return.toFixed(2)}%

[MC] 蒙特卡洛模拟模型结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
均值价格: $${s.mc.mean.toFixed(2)}
中位数价格: $${s.mc.median.toFixed(2)}
标准差: $${s.mc.std.toFixed(2)}
5%-95%置信区间: $${s.mc.percentile_5.toFixed(2)} - $${s.mc.percentile_95.toFixed(2)}
预期收益率: ${s.mc.expected_return.toFixed(2)}%`;

  if (result.prophet) {
    text += `

[Prophet] 时间序列预测模型结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
预测价格: $${result.prophet.mean_price.toFixed(2)}
95%置信区间: $${result.prophet.lower_bound.toFixed(2)} - $${result.prophet.upper_bound.toFixed(2)}
预期收益率: ${result.prophet.return.toFixed(2)}%
风险等级: ${result.prophet.risk_level}`;
  }

  text += `

风险评估
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
年化波动率: ${(result.volatility * 100).toFixed(2)}%`;

  return text;
}

function PredictResult({ result }: { result: SinglePredictResult }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!result.stats_summary) return;
    try {
      await copyToClipboard(buildSummaryText(result));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert("复制失败");
    }
  }

  return (
    <div ref={contentRef}>
      <div className="result-card" style={{ marginTop: "20px" }}>
        <h3 className="result-title">预测结果</h3>

        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">当前价格</div>
            <div className="stat-value">${result.current_price.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">GBM预测价格</div>
            <div className={`stat-value ${result.gbm.return >= 0 ? "positive" : "negative"}`}>
              ${result.gbm.mean_price.toFixed(2)}
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">MC预测价格</div>
            <div className={`stat-value ${result.mc.return >= 0 ? "positive" : "negative"}`}>
              ${result.mc.mean_price.toFixed(2)}
            </div>
          </div>
          {result.prophet && (
            <div className="stat-item">
              <div className="stat-label">Prophet预测价格</div>
              <div className={`stat-value ${result.prophet.return >= 0 ? "positive" : "negative"}`}>
                ${result.prophet.mean_price.toFixed(2)}
              </div>
            </div>
          )}
          <div className="stat-item">
            <div className="stat-label">预期收益率</div>
            <div className={`stat-value ${result.gbm.return >= 0 ? "positive" : "negative"}`}>
              {result.gbm.return.toFixed(2)}%
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">5%分位价格</div>
            <div className="stat-value">${result.gbm.percentile_5.toFixed(2)}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">95%分位价格</div>
            <div className="stat-value">${result.gbm.percentile_95.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {result.stats_summary && (
        <div className="result-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h4>预测统计摘要</h4>
            <button onClick={handleCopy} className="btn-copy">
              {copied ? "✓ 已复制" : "📋 复制"}
            </button>
          </div>
          <pre className="summary-pre">{buildSummaryText(result)}</pre>
        </div>
      )}

      {result.chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.chart}`} alt="预测分布图" style={{ width: "100%" }} />
        </div>
      )}
      {result.mc_paths_chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.mc_paths_chart}`} alt="蒙特卡洛价格轨迹图" style={{ width: "100%" }} />
        </div>
      )}
      {result.mc_cumulative_returns_chart && (
        <div className="result-card">
          <img src={`data:image/png;base64,${result.mc_cumulative_returns_chart}`} alt="累积收益图" style={{ width: "100%" }} />
        </div>
      )}
    </div>
  );
}

export default function SingleTab({ defaultDate }: Props) {
  const [ticker, setTicker] = useState("");
  const [targetDate, setTargetDate] = useState(defaultDate);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SinglePredictResult | null>(null);

  function handleSelect(t: string) {
    setTicker(t);
    setResult(null);
    setError("");
  }

  async function handlePredict() {
    if (!ticker) {
      setError("请先选择股票");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await predictSingle(ticker, targetDate);
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
        <label>选择股票</label>
        <StockSearch onSelect={handleSelect} />
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
        {loading ? "分析中..." : "开始预测"}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>正在分析中，请稍候...</p>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {result && <PredictResult result={result} />}
    </div>
  );
}
