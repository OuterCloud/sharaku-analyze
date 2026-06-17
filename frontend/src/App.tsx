import { useState } from "react";
import BatchTab from "./components/BatchTab";
import Footer from "./components/Footer";
import Header from "./components/Header";
import MarketTab from "./components/MarketTab";
import SingleTab from "./components/SingleTab";
import TechnicalTab from "./components/TechnicalTab";
import WheelTab from "./components/WheelTab";
import { useI18n } from "./i18n/context";

type Tab = "market" | "single" | "batch" | "wheel" | "technical";

const defaultDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  .toISOString()
  .slice(0, 10);

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("market");
  const [selectedTicker, setSelectedTicker] = useState("");
  const { t } = useI18n();

  function handleTickerClick(ticker: string) {
    setSelectedTicker(ticker);
    setActiveTab("single");
  }

  return (
    <div className="container">
      <Header />

      <div className="content">
        <div className="tabs">
          <button
            className={`tab${activeTab === "market" ? " active" : ""}`}
            onClick={() => setActiveTab("market")}
          >
            {t("tab.market")}
          </button>
          <button
            className={`tab${activeTab === "single" ? " active" : ""}`}
            onClick={() => setActiveTab("single")}
          >
            {t("tab.single")}
          </button>
          <button
            className={`tab${activeTab === "batch" ? " active" : ""}`}
            onClick={() => setActiveTab("batch")}
          >
            {t("tab.batch")}
          </button>
          <button
            className={`tab${activeTab === "technical" ? " active" : ""}`}
            onClick={() => setActiveTab("technical")}
          >
            {t("tab.technical")}
          </button>
          <button
            className={`tab${activeTab === "wheel" ? " active" : ""}`}
            onClick={() => setActiveTab("wheel")}
          >
            {t("tab.wheel")}
          </button>
        </div>

        <div className="tab-contents">
          <div style={{ display: activeTab === "market" ? "block" : "none" }}>
            <MarketTab onTickerClick={handleTickerClick} />
          </div>
          <div style={{ display: activeTab === "single" ? "block" : "none" }}>
            <SingleTab defaultDate={defaultDate} initialTicker={selectedTicker} />
          </div>
          <div style={{ display: activeTab === "batch" ? "block" : "none" }}>
            <BatchTab defaultDate={defaultDate} />
          </div>
          <div style={{ display: activeTab === "technical" ? "block" : "none" }}>
            <TechnicalTab />
          </div>
          <div style={{ display: activeTab === "wheel" ? "block" : "none" }}>
            <WheelTab />
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
