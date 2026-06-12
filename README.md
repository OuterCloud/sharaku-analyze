# Sharaku Analyze

股票智能预测分析平台，集成 GBM/蒙特卡洛/Prophet 多模型预测与 Wheel 期权策略盯盘系统。基于 Yahoo Finance 实时数据，支持其覆盖的所有市场标的（美股、港股、A 股、日股、台股等），批量对比分析。

## 功能

- **单股预测**：输入股票代码和目标日期，获取三种模型的综合预测结果
- **批量预测**：多选下拉框选取多只股票，按预期收益率排名对比
- **Wheel 期权策略**：基于 20 日 EMA、波动率、盘面形态，给出 Sell Put / Covered Call 实时决策建议（仅限有期权的美股/港股）
- **动态标的搜索**：通过 Yahoo Finance Search API 实时搜索，支持 Yahoo Finance 覆盖的所有市场
- **可视化图表**：价格分布图、蒙特卡洛路径图、累积收益图

## 预测模型

| 模型 | 说明 | 特点 |
|------|------|------|
| GBM | 几何布朗运动 | 理论定价，考虑漂移和波动 |
| Monte Carlo | 蒙特卡洛模拟 | 路径模拟，提供 VaR/CVaR |
| Prophet | Facebook 时间序列 | 趋势 + 季节性（可选） |

## 快速开始

### 一键部署

```bash
./start.sh
# 自动创建 venv、安装依赖、构建前端、启动服务
# 访问 http://localhost:8000
```

### 手动启动

```bash
# 后端
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py

# 前端（另一个终端）
cd frontend && npm install && npm run build
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/stocks` | GET | 获取已缓存股票列表 |
| `/api/stocks/search?q=` | GET | 搜索股票（本地 + Yahoo Finance） |
| `/api/predict/single` | POST | 单股预测（`ticker`, `target_date`） |
| `/api/predict/batch` | POST | 批量预测（`tickers`, `target_date`） |
| `/api/wheel/analyze` | POST | Wheel 策略分析（`ticker`, `cost_basis`） |

## 配置

复制 `.env.example` 为 `.env`：

```env
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

## 测试

```bash
pytest tests/
```

## 技术栈

- **后端**: Python + FastAPI + uvicorn
- **前端**: React 18 + TypeScript + Vite
- **数据**: Yahoo Finance（yfinance，免费无需 API Key）
- **存储**: SQLite（搜索缓存）+ 内存缓存（预测结果 TTL 1h）

## 项目结构

```
sharaku-analyze/
├── app.py                  # FastAPI 入口
├── start.sh                # 一键部署脚本
├── sharaku/                # 核心 Python 包
│   └── lib/
│       ├── base_predictor.py
│       ├── data_utils.py
│       ├── gbm_predictor.py
│       ├── monte_carlo_predictor.py
│       ├── prophet_predictor.py
│       ├── stock_database.py
│       ├── visualization.py
│       └── wheel_monitor.py
├── frontend/               # React 前端
│   └── src/
│       ├── App.tsx
│       ├── api/predict.ts
│       └── components/
│           ├── SingleTab.tsx
│           ├── BatchTab.tsx
│           ├── WheelTab.tsx
│           └── StockSearch.tsx
├── tests/
└── requirements.txt
```

## License

MIT
