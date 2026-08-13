import { useState } from "react";
import {
  ALL_SECTORS,
  DEFAULT_SCREENER_PARAMS,
  runScreener,
  ScreenerParams,
  ScreenerResultItem,
  ScreenerResponse,
} from "../api/screener";
import { useI18n } from "../i18n/context";

type SortField = "peg" | "roe_pct" | "market_cap_b" | "fcf_m" | "de_pct" | "revenue_growth_pct" | "price_position_pct";
type SortDir = "asc" | "desc";

export default function ScreenerTab() {
  const { t } = useI18n();
  const [params, setParams] = useState<ScreenerParams>({ ...DEFAULT_SCREENER_PARAMS });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScreenerResponse | null>(null);
  const [error, setError] = useState("");
  const [sortField, setSortField] = useState<SortField>("peg");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [showParams, setShowParams] = useState(true);

  async function handleRun() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await runScreener(params);
      if (res.success) {
        setResult(res);
        setShowParams(false);
      } else {
        setError(res.error || t("common.error.analyzeFailed"));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("common.error.requestFailed"));
    } finally {
      setLoading(false);
    }
  }

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir(field === "roe_pct" || field === "revenue_growth_pct" ? "desc" : "asc");
    }
  }

  function getSortedResults(): ScreenerResultItem[] {
    if (!result) return [];
    return [...result.results].sort((a, b) => {
      const av = a[sortField] ?? 0;
      const bv = b[sortField] ?? 0;
      return sortDir === "asc" ? av - bv : bv - av;
    });
  }

  function toggleSector(sector: string) {
    setParams((prev) => {
      const current = prev.sectors;
      if (current.includes(sector)) {
        return { ...prev, sectors: current.filter((s) => s !== sector) };
      }
      return { ...prev, sectors: [...current, sector] };
    });
  }

  function sortIcon(field: SortField) {
    if (sortField !== field) return " ↕";
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  return (
    <div style={{ padding: "0" }}>
      {/* 参数面板 */}
      <div className="result-card" style={{ marginBottom: "16px" }}>
        <div
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
          onClick={() => setShowParams(!showParams)}
        >
          <h3 className="result-title" style={{ margin: 0 }}>
            {t("screener.params.title")}
          </h3>
          <span style={{ color: "#888", fontSize: "14px" }}>{showParams ? "▲" : "▼"}</span>
        </div>

        {showParams && (
          <div style={{ marginTop: "16px" }}>
            {/* 数值参数 */}
            <div className="screener-params-grid">
              <label className="screener-param-item">
                <span className="screener-param-label">{t("screener.params.pegMax")}</span>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="5"
                  value={params.peg_max}
                  onChange={(e) => setParams({ ...params, peg_max: parseFloat(e.target.value) || 1.0 })}
                  className="screener-param-input"
                />
              </label>

              <label className="screener-param-item">
                <span className="screener-param-label">{t("screener.params.roeMin")}</span>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={Math.round(params.roe_min * 100)}
                  onChange={(e) => setParams({ ...params, roe_min: (parseFloat(e.target.value) || 12) / 100 })}
                  className="screener-param-input"
                />
              </label>

              <label className="screener-param-item">
                <span className="screener-param-label">{t("screener.params.marketCap")}</span>
                <input
                  type="number"
                  step="1"
                  min="1"
                  value={Math.round(params.min_market_cap / 1e9)}
                  onChange={(e) => setParams({ ...params, min_market_cap: (parseFloat(e.target.value) || 10) * 1e9 })}
                  className="screener-param-input"
                />
              </label>

              <label className="screener-param-item">
                <span className="screener-param-label">{t("screener.params.deMax")}</span>
                <input
                  type="number"
                  step="10"
                  min="0"
                  max="500"
                  value={params.de_max}
                  onChange={(e) => setParams({ ...params, de_max: parseFloat(e.target.value) || 100 })}
                  className="screener-param-input"
                />
              </label>
            </div>

            {/* FCF 复选框 */}
            <div style={{ marginTop: "12px" }}>
              <label className="screener-param-checkbox">
                <input
                  type="checkbox"
                  checked={params.fcf_positive}
                  onChange={(e) => setParams({ ...params, fcf_positive: e.target.checked })}
                />
                <span>{t("screener.params.fcfPositive")}</span>
              </label>
            </div>

            {/* 板块选择 */}
            <div style={{ marginTop: "12px" }}>
              <span className="screener-param-label">{t("screener.params.sectors")}</span>
              <div className="screener-sector-chips">
                {ALL_SECTORS.map((sector) => (
                  <button
                    key={sector}
                    className={`screener-sector-chip${params.sectors.includes(sector) ? " active" : ""}`}
                    onClick={() => toggleSector(sector)}
                  >
                    {sector}
                  </button>
                ))}
              </div>
            </div>

            {/* 执行按钮 */}
            <div style={{ marginTop: "16px", textAlign: "center" }}>
              <button
                className={`btn${loading ? " loading" : ""}`}
                onClick={handleRun}
                disabled={loading || params.sectors.length === 0}
                style={{ minWidth: "200px" }}
              >
                {loading ? t("screener.running") : t("screener.run")}
              </button>
              {params.sectors.length === 0 && (
                <p style={{ color: "#e74c3c", fontSize: "12px", marginTop: "6px" }}>
                  {t("screener.error.noSectors")}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="result-card" style={{ textAlign: "center", padding: "40px 20px" }}>
          <p style={{ marginTop: "0", color: "#888" }}>{t("screener.loading")}</p>
          <p style={{ color: "#666", fontSize: "12px" }}>{t("screener.loadingHint")}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="result-card" style={{ borderLeft: "3px solid #e74c3c" }}>
          <p style={{ color: "#e74c3c" }}>{error}</p>
        </div>
      )}

      {/* Results */}
      {result && result.results.length > 0 && (
        <div className="result-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
            <h3 className="result-title" style={{ margin: 0 }}>
              {t("screener.result.title")}
            </h3>
            <span style={{ color: "#888", fontSize: "13px" }}>
              {t("screener.result.summary")
                .replace("{scanned}", result.total_scanned.toString())
                .replace("{found}", result.results.length.toString())}
            </span>
          </div>

          {/* 策略说明 */}
          <div className="screener-explanation">
            <p className="screener-explanation-title">{t("screener.explain.title")}</p>
            <p className="screener-explanation-body">{t("screener.explain.body")}</p>
            <div className="screener-legend">
              <span className="screener-legend-item">
                <span className="screener-legend-dot good" />PEG — {t("screener.explain.peg")}
              </span>
              <span className="screener-legend-item">
                <span className="screener-legend-dot good" />ROE — {t("screener.explain.roe")}
              </span>
              <span className="screener-legend-item">
                <span className="screener-legend-dot neutral" />D/E — {t("screener.explain.de")}
              </span>
              <span className="screener-legend-item">
                <span className="screener-legend-dot neutral" />FCF — {t("screener.explain.fcf")}
              </span>
              <span className="screener-legend-item">
                <span className="screener-legend-dot neutral" />{t("screener.table.pricePos")} — {t("screener.explain.pricePos")}
              </span>
            </div>
          </div>

          <div className="screener-table-wrapper">
            <table className="screener-table">
              <thead>
                <tr>
                  <th className="sticky-col col-num">#</th>
                  <th className="sticky-col col-symbol">{t("screener.table.symbol")}</th>
                  <th>{t("screener.table.name")}</th>
                  <th>{t("screener.table.sector")}</th>
                  <th className="sortable" onClick={() => handleSort("market_cap_b")}>
                    {t("screener.table.marketCap")}{sortIcon("market_cap_b")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("peg")}>
                    PEG{sortIcon("peg")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("roe_pct")}>
                    ROE{sortIcon("roe_pct")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("fcf_m")}>
                    FCF{sortIcon("fcf_m")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("de_pct")}>
                    D/E{sortIcon("de_pct")}
                  </th>
                  <th className="sortable" onClick={() => handleSort("revenue_growth_pct")}>
                    {t("screener.table.growth")}{sortIcon("revenue_growth_pct")}
                  </th>
                  <th className="sortable sticky-col col-price-pos" onClick={() => handleSort("price_position_pct")}>
                    {t("screener.table.pricePos")}{sortIcon("price_position_pct")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {getSortedResults().map((item, idx) => (
                  <tr key={item.symbol}>
                    <td className="sticky-col col-num row-num">{idx + 1}</td>
                    <td className="sticky-col col-symbol symbol-cell">
                      <strong>{item.symbol}</strong>
                    </td>
                    <td className="name-cell" title={item.name}>
                      {item.name.length > 20 ? item.name.slice(0, 20) + "…" : item.name}
                    </td>
                    <td>
                      <span className="sector-badge">{item.sector}</span>
                    </td>
                    <td className="num-cell">${item.market_cap_b}B</td>
                    <td className="num-cell highlight-good">{item.peg}</td>
                    <td className="num-cell highlight-good">{item.roe_pct}%</td>
                    <td className="num-cell">{item.fcf_m != null ? `$${item.fcf_m}M` : "N/A"}</td>
                    <td className="num-cell">{item.de_pct != null ? `${item.de_pct}%` : "N/A"}</td>
                    <td className="num-cell">
                      {item.revenue_growth_pct != null ? (
                        <span style={{ color: item.revenue_growth_pct >= 0 ? "#27ae60" : "#e74c3c" }}>
                          {item.revenue_growth_pct > 0 ? "+" : ""}{item.revenue_growth_pct}%
                        </span>
                      ) : "N/A"}
                    </td>
                    <td className="num-cell sticky-col col-price-pos">
                      {item.price_position_pct != null ? (
                        <div className="price-pos-cell">
                          <div className="price-pos-bar">
                            <div
                              className="price-pos-fill"
                              style={{
                                width: `${item.price_position_pct}%`,
                                background: item.price_position_pct > 80 ? "#e74c3c"
                                  : item.price_position_pct > 60 ? "#ff9800"
                                  : "#27ae60",
                              }}
                            />
                          </div>
                          <span className={`price-pos-text${item.price_position_pct > 80 ? " high" : item.price_position_pct < 30 ? " low" : ""}`}>
                            {item.price_position_pct}%
                          </span>
                        </div>
                      ) : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No results */}
      {result && result.results.length === 0 && (
        <div className="result-card" style={{ textAlign: "center", padding: "40px" }}>
          <p style={{ color: "#888", fontSize: "16px" }}>{t("screener.noResults")}</p>
          <p style={{ color: "#666", fontSize: "13px" }}>{t("screener.noResultsHint")}</p>
        </div>
      )}
    </div>
  );
}
