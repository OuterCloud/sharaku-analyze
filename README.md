# Sharaku Analyze

股票智能预测分析平台，集成 GBM/蒙特卡洛/Prophet 多模型预测与 Wheel 期权策略盯盘系统。基于 Yahoo Finance 实时数据，支持多市场标的（美股、港股、A 股、日股、台股、韩股、英股等）。

## 功能

- **单股预测**：输入股票代码和目标日期，获取三种模型的综合预测结果
- **批量预测**：多选下拉框选取多只股票，按预期收益率排名对比
- **技术分析**：7 大指标 + 15 种 K 线形态识别，输出 0-100 综合评分
- **Wheel 期权策略**：基于 20 日 EMA、波动率、盘面形态，给出 Sell Put / Covered Call 实时决策建议（仅限有期权链的标的）
- **投资顾问（LLM）**：结合个人知识库笔记 + 全维度市场数据，对话式给出好价格判断、入场点设计、期权策略参数
- **动态标的搜索**：通过 Yahoo Finance Search API 实时搜索，自动识别市场（US/HK/CN/JP/TW/KR/UK 等）
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
| `/api/technical/analyze` | POST | 技术分析（`ticker`, `lang`） |
| `/api/advisor/status` | GET | 顾问模块状态与知识库概况 |
| `/api/advisor/chat` | POST | 投资顾问对话（SSE 流式） |

## 配置

复制 `.env.example` 为 `.env`：

```env
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# LLM 投资顾问（不配置则该模块不可用，其他功能不受影响）
LLM_API_KEY=your-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=claude-opus-5
LLM_MAX_TOKENS=8000
LLM_TEMPERATURE=0.3

KNOWLEDGE_DIR=knowledge
```

## 投资顾问模块

结合三层信息给出决策建议：

1. **个人知识库** — `knowledge/` 目录下的 Markdown 笔记（投资纪律、复盘教训、估值标准），优先级最高
2. **实时市场数据** — 价格区间位置、7 大技术指标、支撑阻力位、GBM/MC 统计预测、基本面估值、分析师目标价、期权链（IV/权利金/未平仓）、财报日历、Wheel 机器决策
3. **决策框架** — 系统提示词强制要求输出可执行参数（具体价位、仓位比例、行权价、到期日）

### 使用

1. 把你的投资笔记放进 `knowledge/` 目录（`.md` 文件，支持子目录）
2. 在"投资顾问"页选择标的，可选填持仓成本价
3. 点预设问题或自由提问，回答流式输出

保存笔记后立即生效，无需重启（按文件 mtime 自动刷新）。详见 `knowledge/README.md`。

## 测试

```bash
# 后端
pytest tests/

# 前端
cd frontend && npm test && npm run typecheck
```

## 技术栈

- **后端**: Python + FastAPI + uvicorn
- **前端**: React 18 + TypeScript + Vite
- **数据**: Yahoo Finance（yfinance，免费无需 API Key）
- **LLM**: OpenAI 兼容接口（可配置 base_url，默认 claude-opus-5）
- **存储**: SQLite（搜索缓存）+ 磁盘缓存（预测结果 TTL 1h，顾问上下文 TTL 5min）

## 项目结构

```
sharaku-analyze/
├── app.py                  # FastAPI 入口
├── start.sh                # 一键部署脚本
├── knowledge/              # 个人投资笔记（投资顾问知识库）
├── sharaku/                # 核心 Python 包
│   └── lib/
│       ├── advisor.py            # LLM 投资顾问
│       ├── knowledge_base.py     # 知识库加载与检索
│       ├── market_context.py     # 全维度市场数据汇总
│       ├── base_predictor.py
│       ├── data_utils.py
│       ├── gbm_predictor.py
│       ├── monte_carlo_predictor.py
│       ├── prophet_predictor.py
│       ├── stock_database.py
│       ├── technical_analyzer.py
│       ├── visualization.py
│       └── wheel_monitor.py
├── frontend/               # React 前端
│   └── src/
│       ├── App.tsx
│       ├── api/
│       │   ├── predict.ts
│       │   └── advisor.ts        # SSE 流式客户端
│       ├── utils/
│       │   ├── currency.ts       # 多市场货币符号
│       │   └── markdown.ts       # 零依赖安全渲染器
│       └── components/
│           ├── MarketTab.tsx
│           ├── SingleTab.tsx
│           ├── BatchTab.tsx
│           ├── TechnicalTab.tsx
│           ├── WheelTab.tsx
│           ├── AdvisorTab.tsx
│           └── StockSearch.tsx
├── tests/
└── requirements.txt
```

## License

MIT
