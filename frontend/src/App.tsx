import { useState } from "react";
import BatchTab from "./components/BatchTab";
import Footer from "./components/Footer";
import Header from "./components/Header";
import SingleTab from "./components/SingleTab";
import TechnicalTab from "./components/TechnicalTab";
import WheelTab from "./components/WheelTab";

type Tab = "single" | "batch" | "wheel" | "technical";

const defaultDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  .toISOString()
  .slice(0, 10);

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("single");

  return (
    <div className="container">
      <Header />

      <div className="content">
        <div className="tabs">
          <button
            className={`tab${activeTab === "single" ? " active" : ""}`}
            onClick={() => setActiveTab("single")}
          >
            单股预测
          </button>
          <button
            className={`tab${activeTab === "batch" ? " active" : ""}`}
            onClick={() => setActiveTab("batch")}
          >
            批量预测
          </button>
          <button
            className={`tab${activeTab === "technical" ? " active" : ""}`}
            onClick={() => setActiveTab("technical")}
          >
            技术分析
          </button>
          <button
            className={`tab${activeTab === "wheel" ? " active" : ""}`}
            onClick={() => setActiveTab("wheel")}
          >
            Wheel策略
          </button>
        </div>

        <div className="tab-contents">
          <div style={{ display: activeTab === "single" ? "block" : "none" }}>
            <SingleTab defaultDate={defaultDate} />
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
