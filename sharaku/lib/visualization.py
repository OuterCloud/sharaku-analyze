"""
Visualization utilities for stock prediction charts.

Generates base64-encoded PNG charts for web display.
"""

import base64
import io

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from loguru import logger

matplotlib.use("Agg")

# Font configuration
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def generate_prediction_chart(
    ticker, current_price, gbm_prices, mc_prices, target_date
):
    """生成单个股票的预测图表，返回 (base64, stats_data)"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"{ticker} Price Prediction (Target: {target_date})",
        fontsize=16,
        fontweight="bold",
    )

    # 1. GBM价格分布
    axes[0, 0].hist(gbm_prices, bins=50, alpha=0.7, color="skyblue", edgecolor="black")
    axes[0, 0].axvline(
        current_price, color="green", linestyle="-", linewidth=2,
        label=f"Current: ${current_price:.2f}",
    )
    axes[0, 0].axvline(
        np.mean(gbm_prices), color="red", linestyle="--", linewidth=2,
        label=f"Mean: ${np.mean(gbm_prices):.2f}",
    )
    axes[0, 0].set_xlabel("Price ($)")
    axes[0, 0].set_ylabel("Frequency")
    axes[0, 0].set_title("GBM Price Distribution")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. MC价格分布
    axes[0, 1].hist(mc_prices, bins=50, alpha=0.7, color="lightgreen", edgecolor="black")
    axes[0, 1].axvline(
        current_price, color="green", linestyle="-", linewidth=2,
        label=f"Current: ${current_price:.2f}",
    )
    axes[0, 1].axvline(
        np.mean(mc_prices), color="red", linestyle="--", linewidth=2,
        label=f"Mean: ${np.mean(mc_prices):.2f}",
    )
    axes[0, 1].set_xlabel("Price ($)")
    axes[0, 1].set_ylabel("Frequency")
    axes[0, 1].set_title("MC Price Distribution")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # 3. 价格百分位数对比
    percentiles = [5, 25, 50, 75, 95]
    gbm_percentiles = [np.percentile(gbm_prices, p) for p in percentiles]
    mc_percentiles = [np.percentile(mc_prices, p) for p in percentiles]

    x = np.arange(len(percentiles))
    width = 0.35
    axes[1, 0].bar(x - width / 2, gbm_percentiles, width, label="GBM", alpha=0.7)
    axes[1, 0].bar(x + width / 2, mc_percentiles, width, label="MC", alpha=0.7)
    axes[1, 0].axhline(current_price, color="green", linestyle="--", linewidth=1, label="Current")
    axes[1, 0].set_xlabel("Percentile")
    axes[1, 0].set_ylabel("Price ($)")
    axes[1, 0].set_title("Price Percentile Comparison")
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels([f"{p}%" for p in percentiles])
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3, axis="y")

    # 4. 统计摘要
    axes[1, 1].axis("off")
    summary_text = f"""
    Prediction Summary
    {'=' * 30}

    [GBM] Geometric Brownian Motion
    Mean: ${np.mean(gbm_prices):.2f}
    Median: ${np.median(gbm_prices):.2f}
    Std Dev: ${np.std(gbm_prices):.2f}
    5%-95% Range:
      ${np.percentile(gbm_prices, 5):.2f} - ${np.percentile(gbm_prices, 95):.2f}

    [MC] Monte Carlo Simulation
    Mean: ${np.mean(mc_prices):.2f}
    Median: ${np.median(mc_prices):.2f}
    Std Dev: ${np.std(mc_prices):.2f}
    5%-95% Range:
      ${np.percentile(mc_prices, 5):.2f} - ${np.percentile(mc_prices, 95):.2f}
    """
    axes[1, 1].text(0.1, 0.5, summary_text, fontsize=10, verticalalignment="center")

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()

    stats_data = {
        "gbm": {
            "mean": float(np.mean(gbm_prices)),
            "median": float(np.median(gbm_prices)),
            "std": float(np.std(gbm_prices)),
            "percentile_5": float(np.percentile(gbm_prices, 5)),
            "percentile_95": float(np.percentile(gbm_prices, 95)),
            "expected_return": float(
                ((np.mean(gbm_prices) - current_price) / current_price * 100)
            ),
        },
        "mc": {
            "mean": float(np.mean(mc_prices)),
            "median": float(np.median(mc_prices)),
            "std": float(np.std(mc_prices)),
            "percentile_5": float(np.percentile(mc_prices, 5)),
            "percentile_95": float(np.percentile(mc_prices, 95)),
            "expected_return": float(
                ((np.mean(mc_prices) - current_price) / current_price * 100)
            ),
        },
    }

    return image_base64, stats_data


def generate_monte_carlo_paths_chart(ticker, current_price, mc_predictions, target_date):
    """生成蒙特卡洛价格路径轨迹图"""
    price_paths = mc_predictions.get("price_paths", [])
    if price_paths is None or (hasattr(price_paths, "__len__") and len(price_paths) == 0):
        return ""

    price_paths = np.array(price_paths)
    n_paths, n_days = price_paths.shape
    time_axis = np.arange(n_days)

    fig, ax = plt.subplots(figsize=(12, 8))

    n_show = min(100, n_paths)
    for i in range(n_show):
        ax.plot(time_axis, price_paths[i], color="blue", alpha=0.15, linewidth=0.8)

    percentiles = [5, 25, 50, 75, 95]
    colors = ["red", "orange", "green", "orange", "red"]
    labels = ["5th Pctl", "25th Pctl", "Median", "75th Pctl", "95th Pctl"]

    for p, color, label in zip(percentiles, colors, labels):
        path = np.percentile(price_paths, p, axis=0)
        ax.plot(time_axis, path, color=color, linewidth=2.5, label=label, alpha=0.9)

    mean_path = np.mean(price_paths, axis=0)
    ax.plot(time_axis, mean_path, color="darkblue", linewidth=3, label="Mean Path", alpha=0.95)

    ax.axhline(y=current_price, color="black", linestyle="--", linewidth=2,
               label=f"Current: ${current_price:.2f}")

    ax.set_title(f"{ticker} MC Price Paths (n={n_paths:,})", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trading Day", fontsize=12)
    ax.set_ylabel("Price ($)", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=10)
    ax.set_ylim(bottom=0)

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()

    return image_base64


def generate_cumulative_returns_chart(ticker, current_price, mc_predictions, target_date):
    """生成累积收益率路径图"""
    price_paths = mc_predictions.get("price_paths", [])
    if price_paths is None or (hasattr(price_paths, "__len__") and len(price_paths) == 0):
        return ""

    price_paths = np.array(price_paths)
    n_paths, n_days = price_paths.shape
    time_axis = np.arange(n_days)

    cumulative_returns = (price_paths / current_price - 1) * 100

    fig, ax = plt.subplots(figsize=(12, 8))

    for i in range(min(50, n_paths)):
        ax.plot(time_axis, cumulative_returns[i], color="blue", alpha=0.15, linewidth=0.8)

    for p, color, label in zip([5, 50, 95], ["red", "green", "red"], ["5th", "Median", "95th"]):
        path = np.percentile(cumulative_returns, p, axis=0)
        ax.plot(time_axis, path, color=color, linewidth=2.5, label=label, alpha=0.9)

    ax.axhline(0, color="black", linestyle="--", linewidth=2, label="Break Even")

    ax.set_title(
        f"{ticker} Cumulative Return Paths\n({n_paths:,} Simulated Paths, Target: {target_date})",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Trading Day", fontsize=12)
    ax.set_ylabel("Cumulative Return (%)", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=10)

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()

    return image_base64


def generate_batch_chart(results, target_date):
    """生成批量预测对比图表"""
    if not results:
        return ""

    df = pd.DataFrame(results)
    df = df.sort_values("gbm_return", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f"Batch Prediction Comparison (Target: {target_date})", fontsize=16, fontweight="bold")

    # 1. 预期收益率对比
    colors = ["red" if r < 0 else "green" for r in df["gbm_return"]]
    axes[0].barh(df["ticker"], df["gbm_return"], color=colors, alpha=0.7)
    axes[0].set_xlabel("Expected Return (%)")
    axes[0].set_title("Expected Return Ranking")
    axes[0].axvline(0, color="black", linestyle="-", linewidth=0.8)
    axes[0].grid(True, alpha=0.3, axis="x")

    # 2. 价格预测对比
    x = np.arange(len(df))
    width = 0.35
    axes[1].bar(x - width / 2, df["current_price"], width, label="Current", alpha=0.7)
    axes[1].bar(x + width / 2, df["gbm_mean_price"], width, label="Predicted", alpha=0.7)
    axes[1].set_xlabel("Stock")
    axes[1].set_ylabel("Price ($)")
    axes[1].set_title("Price Comparison")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["ticker"])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()

    return image_base64
