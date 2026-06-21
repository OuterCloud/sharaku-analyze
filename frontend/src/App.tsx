import { useEffect, useRef, useState } from "react";
import BatchTab from "./components/BatchTab";
import Footer from "./components/Footer";
import Header from "./components/Header";
import MarketTab from "./components/MarketTab";
import SingleTab from "./components/SingleTab";
import TechnicalTab from "./components/TechnicalTab";
import WheelTab from "./components/WheelTab";
import { useI18n } from "./i18n/context";

type Tab = "market" | "single" | "batch" | "wheel" | "technical";

const TABS: Tab[] = ["market", "single", "batch", "technical", "wheel"];

const defaultDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  .toISOString()
  .slice(0, 10);

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("market");
  const [selectedTicker, setSelectedTicker] = useState("");
  const { t } = useI18n();

  // Global keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey;
      // Cmd/Ctrl + 1~5: switch tabs
      if (meta && e.key >= "1" && e.key <= "5") {
        e.preventDefault();
        setActiveTab(TABS[parseInt(e.key) - 1]);
        return;
      }
      // "/" to focus search (when not in input)
      if (e.key === "/" && !isInputFocused()) {
        e.preventDefault();
        const searchInput = document.querySelector<HTMLInputElement>(".stock-search-input");
        searchInput?.focus();
      }
    }
    function isInputFocused() {
      const el = document.activeElement;
      return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Swipe gesture to switch tabs (mobile)
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    function onTouchStart(e: TouchEvent) {
      const t = e.touches[0];
      touchStart.current = { x: t.clientX, y: t.clientY };
    }
    function onTouchEnd(e: TouchEvent) {
      if (!touchStart.current) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - touchStart.current.x;
      const dy = t.clientY - touchStart.current.y;
      touchStart.current = null;
      // Only trigger if horizontal swipe is dominant and > 80px
      if (Math.abs(dx) < 80 || Math.abs(dy) > Math.abs(dx) * 0.6) return;
      setActiveTab((prev) => {
        const idx = TABS.indexOf(prev);
        if (dx < 0 && idx < TABS.length - 1) return TABS[idx + 1]; // swipe left → next
        if (dx > 0 && idx > 0) return TABS[idx - 1]; // swipe right → prev
        return prev;
      });
    }
    document.addEventListener("touchstart", onTouchStart, { passive: true });
    document.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onTouchStart);
      document.removeEventListener("touchend", onTouchEnd);
    };
  }, []);

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
