// Stock Screener API client

export interface ScreenerParams {
  peg_max: number;
  roe_min: number;
  min_market_cap: number;
  de_max: number;
  fcf_positive: boolean;
  sectors: string[];
}

export interface ScreenerResultItem {
  symbol: string;
  name: string;
  sector: string;
  market_cap_b: number;
  peg: number;
  forward_pe: number | null;
  trailing_pe: number | null;
  roe_pct: number;
  fcf_m: number | null;
  de_pct: number | null;
  dividend_yield_pct: number | null;
  revenue_growth_pct: number | null;
  profit_margin_pct: number | null;
  current_price: number | null;
  week52_high: number | null;
  week52_low: number | null;
  price_position_pct: number | null;
}

export interface ScreenerResponse {
  success: boolean;
  total_scanned: number;
  results: ScreenerResultItem[];
  params_used: {
    min_market_cap: number;
    sectors: string[];
    peg_range: string;
    roe_min: number;
    fcf_positive: boolean;
    de_max: number;
  };
  error?: string;
}

export const DEFAULT_SCREENER_PARAMS: ScreenerParams = {
  peg_max: 1.0,
  roe_min: 0.12,
  min_market_cap: 10_000_000_000,
  de_max: 100.0,
  fcf_positive: true,
  sectors: ["Healthcare", "Technology", "Financial Services", "Industrials", "Energy"],
};

export const ALL_SECTORS = [
  "Technology",
  "Healthcare",
  "Financial Services",
  "Industrials",
  "Energy",
  "Consumer Cyclical",
  "Consumer Defensive",
  "Communication Services",
  "Utilities",
  "Real Estate",
  "Basic Materials",
];

export async function runScreener(params: ScreenerParams): Promise<ScreenerResponse> {
  const formData = new FormData();
  formData.append("peg_max", params.peg_max.toString());
  formData.append("roe_min", params.roe_min.toString());
  formData.append("min_market_cap", params.min_market_cap.toString());
  formData.append("de_max", params.de_max.toString());
  formData.append("fcf_positive", params.fcf_positive ? "1" : "0");
  formData.append("sectors", params.sectors.join(","));

  const resp = await fetch("/api/screener/run", {
    method: "POST",
    body: formData,
  });

  if (!resp.ok) {
    throw new Error(`Screener request failed: ${resp.status}`);
  }

  return resp.json();
}
