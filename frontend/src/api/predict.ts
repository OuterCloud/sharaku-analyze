export interface Stock {
  ticker: string
  name: string
  stock_type: string
  sector?: string
}

export interface StatsSummaryModel {
  mean: number
  median: number
  std: number
  percentile_5: number
  percentile_95: number
  expected_return: number
}

export interface StatsSummary {
  gbm: StatsSummaryModel
  mc: StatsSummaryModel
}

export interface SinglePredictResult {
  success: boolean
  ticker: string
  name: string
  current_price: number
  target_date: string
  trading_days: number
  gbm: { mean_price: number; median_price: number; return: number; percentile_5: number; percentile_95: number }
  mc: { mean_price: number; median_price: number; return: number; percentile_5: number; percentile_95: number }
  prophet?: { mean_price: number; return: number; lower_bound: number; upper_bound: number; risk_level: string }
  chart?: string
  mc_paths_chart?: string
  mc_cumulative_returns_chart?: string
  volatility: number
  stats_summary?: StatsSummary
  error?: string
}

export interface BatchResultItem {
  ticker: string
  name: string
  current_price: number
  gbm_mean_price: number
  gbm_return: number
  mc_mean_price: number
  mc_return: number
  volatility: number
}

export interface BatchPredictResult {
  success: boolean
  target_date: string
  results: BatchResultItem[]
  chart?: string
  error?: string
}

async function post(path: string, data: Record<string, string>): Promise<Response> {
  const body = new FormData()
  Object.entries(data).forEach(([k, v]) => body.append(k, v))
  return fetch(path, { method: 'POST', body })
}

export async function searchStocks(q: string): Promise<Stock[]> {
  const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(q)}`)
  const data = await res.json()
  return data.success ? data.stocks : []
}

export async function validateTicker(ticker: string): Promise<{ success: boolean; stock?: Stock; error?: string }> {
  const res = await fetch(`/api/stocks/validate?ticker=${encodeURIComponent(ticker)}`)
  return res.json()
}

export async function getStocks(): Promise<Stock[]> {
  const res = await fetch('/api/stocks')
  const data = await res.json()
  return data.success ? data.stocks : []
}

export async function predictSingle(ticker: string, targetDate: string): Promise<SinglePredictResult> {
  const res = await post('/api/predict/single', { ticker, target_date: targetDate })
  return res.json()
}

export async function predictBatch(tickers: string, targetDate: string): Promise<BatchPredictResult> {
  const res = await post('/api/predict/batch', { tickers, target_date: targetDate })
  return res.json()
}

// Wheel Strategy
export interface WheelDecision {
  status: string
  label: string
  reason: string
  recommended_strike: number | null
  strike_distance_pct: number | null
  cash_required?: number
  cost_basis?: number
}

export interface WheelResult {
  success: boolean
  ticker: string
  current_price: number
  ema_20: number
  ema_deviation: number
  ema_trend: number
  volatility: number
  intra_drop: number
  intra_change: number
  gap_and_change: number
  is_v_shape: boolean
  today_open: number
  today_high: number
  today_low: number
  prev_close: number
  sell_put: WheelDecision
  covered_call: WheelDecision
  error?: string
}

export async function analyzeWheel(ticker: string, costBasis: number): Promise<WheelResult> {
  const res = await post('/api/wheel/analyze', { ticker, cost_basis: String(costBasis) })
  return res.json()
}
