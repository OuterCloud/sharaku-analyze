# Sharaku Analyze

港美股智能预测分析系统。基于 GBM（几何布朗运动）、蒙特卡洛模拟和 Prophet 时间序列模型进行股价预测。

## 功能

- **单股预测**：输入股票代码和目标日期，获取三种模型的综合预测结果
- **批量预测**：同时预测多只股票，按预期收益率排名
- **可视化图表**：价格分布图、蒙特卡洛路径图、累积收益图
- **股票管理**：SQLite 数据库管理股票列表

## 预测模型

| 模型 | 说明 | 特点 |
|------|------|------|
| GBM | 几何布朗运动 | 理论定价，考虑漂移和波动 |
| Monte Carlo | 蒙特卡洛模拟 | 路径模拟，提供 VaR/CVaR |
| Prophet | Facebook 时间序列 | 趋势 + 季节性（可选） |

## 快速开始

### 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

### 前端

```bash
cd frontend
npm install
npm run dev    # 开发模式
npm run build  # 构建生产版本
```

### 一键启动（生产）

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python app.py
# 访问 http://localhost:8000
```

## API 文档

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/stocks` | GET | 获取股票列表 |
| `/api/stocks/search` | GET | 搜索股票（参数: `q`） |
| `/api/stocks` | POST | 添加股票 |
| `/api/predict/single` | POST | 单股预测（参数: `ticker`, `target_date`） |
| `/api/predict/batch` | POST | 批量预测（参数: `tickers`, `target_date`） |

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
- **数据**: yfinance（免费，无需 API Key）
- **存储**: SQLite（股票列表）+ 内存缓存（预测结果）
- **预测**: NumPy + pandas + matplotlib

## 项目结构

```
sharaku-analyze/
├── app.py              # FastAPI 入口
├── sharaku/            # 核心 Python 包
│   ├── config.py
│   └── lib/
│       ├── base_predictor.py
│       ├── data_utils.py
│       ├── gbm_predictor.py
│       ├── monte_carlo_predictor.py
│       ├── prophet_predictor.py
│       ├── stock_database.py
│       └── visualization.py
├── frontend/           # React 前端
│   └── src/
│       ├── App.tsx
│       ├── api/predict.ts
│       └── components/
├── tests/              # 测试
└── requirements.txt
```

## License

MIT
