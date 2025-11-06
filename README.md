<div align="center">

# 🏆 AI Quantitative Trading Arena
### AI量化竞技场

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[English](#-english-version) | [中文](#-中文版本)

*A multi-AI quantitative trading competition platform powered by LangGraph*

[Demo](#-demo) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Architecture](#-architecture)

</div>

---

## 📑 目录 | Table of Contents

- [中文版本](#-中文版本)
  - [项目简介](#项目简介)
  - [核心特性](#核心特性)
  - [快速开始](#快速开始)
  - [部署指南](#部署指南)
  - [配置说明](#配置说明)
  - [项目结构](#项目结构)
  - [常见问题](#常见问题)
- [English Version](#english)
  - [Introduction](#-introduction)
  - [Key Features](#-key-features)
  - [Competing AI Models](#-competing-ai-models)
  - [Quick Start](#-quick-start)
  - [Project Structure](#-project-structure)
  - [Usage](#-usage)
  - [Configuration](#️-configuration)
  - [Architecture](#-architecture)

---

<a id="-中文版本"></a>
## 🇨🇳 中文版本

### 项目简介

**AI量化竞技场**是一个创新的多AI模型竞技平台，让**5个顶级大语言模型**同时参与股票交易对决：

- 🤖 **DeepSeek-V3.2** - 深度推理能力
- 🧠 **Qwen3-Max** - 综合能力优秀
- 🎯 **GLM-4.6** - 中文理解专家
- 📚 **Kimi-K2** - 长文本处理
- 🚀 **Doubao-1.6** - 创新决策

通过**LangGraph Agent**架构实现智能决策和自我反思，使用**真实A股历史数据**进行回测，实时竞技排名。

### 核心特性

#### 🎮 AI竞技系统
- ✅ **多模型对决** - 5个顶级AI模型同台竞技
- ✅ **实时排名** - 动态展示收益率、胜率排行榜
- ✅ **公平竞争** - 相同初始资金、相同市场数据
- ✅ **透明决策** - 查看每个AI的思考过程和理由

#### 🧠 智能决策引擎
- ✅ **LangGraph架构** - 基于状态机的Agent决策流程
- ✅ **自我反思** - AI定期总结经验，优化策略
- ✅ **多因子分析** - 综合估值、技术、基本面多维度决策
- ✅ **简化提示词** - 参考AI-Trader成功经验，让AI更自由思考

#### 📊 数据与可视化
- ✅ **真实数据** - Baostock免费A股完整历史数据（2015至今）
- ✅ **新闻集成** - AkShare市场新闻和个股公告
- ✅ **ECharts图表** - 资金曲线、持仓分析、交易详情
- ✅ **实时更新** - WebSocket实时推送交易进展

#### 💼 风险控制
- ✅ **仓位管理** - 单股持仓上限、总仓位控制
- ✅ **止损止盈** - 可配置的止损止盈比例
- ✅ **资金保护** - 现金安全线、最小交易金额
- ✅ **风控拒绝** - 不合规交易自动拦截

### 🎮 参赛AI模型

| 模型 | 提供商 | API接口 | 模型版本 | 特点 |
|------|--------|---------|----------|------|
| 🤖 DeepSeek-V3.2 | DeepSeek | `api.deepseek.com` | `deepseek-chat` | 强大推理能力 |
| 🧠 Qwen3-Max | 阿里云 | `dashscope.aliyuncs.com` | `qwen3-max` | 综合能力强 |
| 🎯 GLM-4.6 | 智谱AI | `open.bigmodel.cn` | `glm-4.6` | 中文理解优秀 |
| 📚 Kimi-K2 | 月之暗面 | `api.moonshot.cn` | `kimi-k2-turbo-preview` | 长文本处理 |
| 🚀 Doubao-1.6 | 字节跳动 | `ark.cn-beijing.volces.com` | `doubao-seed-1-6-251015` | 创新决策 |

### 🚀 快速开始

#### 1. 环境要求

- **操作系统**: Windows 10/11, macOS, Linux
- **Python**: 3.10+ (推荐 3.13.1)
- **内存**: 建议 8GB+
- **网络**: 需要访问AI API和Baostock数据源

#### 2. 获取代码

**方式1：Git克隆（推荐）**
```bash
git clone https://github.com/gtd138/QuantArenaOSS.git
cd QuantArenaOSS
```

**方式2：直接下载**
- 访问 [Releases](https://github.com/YOUR_USERNAME/LHArena/releases)
- 下载最新版本的源码压缩包
- 解压到本地目录

#### 3. 安装依赖

**基本安装：**
```bash
pip install -r requirements.txt
```

<details>
<summary>📚 主要依赖包列表</summary>

| 包名 | 版本 | 用途 |
|------|------|------|
| `fastapi` | 0.100+ | 后端API框架 |
| `uvicorn` | Latest | ASGI服务器 |
| `langchain` | Latest | AI应用框架 |
| `langgraph` | Latest | Agent状态机 |
| `openai` | Latest | 统一LLM调用接口 |
| `pandas` | Latest | 数据处理 |
| `baostock` | Latest | A股数据源 |
| `akshare` | Latest | 新闻数据源 |

</details>

#### 4. 配置API密钥 🔑

**第1步：获取API密钥**

| 提供商 | 注册链接 | 费用 | 备注 |
|------|----------|------|------|
| DeepSeek | https://platform.deepseek.com | 低价 | 推荐，性价比高 |
| 阿里云 | https://dashscope.aliyuncs.com | 有免费额度 | Qwen系列 |
| 智谱AI | https://open.bigmodel.cn | 有免费额度 | GLM系列 |
| 月之暗面 | https://platform.moonshot.cn | 付费 | Kimi系列 |
| 字节跳动 | https://www.volcengine.com | 付费 | Doubao系列 |

**第2步：编辑配置文件**

复制 `config.json.example` 为 `config.json`（如果有），或直接编辑 `config.json`：

```json
{
  "deepseek": {
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
  },
  "qwen": {
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3-max"
  },
  "glm": {
    "api_key": "xxxxxxxx.xxxxxxxxxx",
    "api_base": "https://open.bigmodel.cn/api/paas/v4",
    "model": "glm-4.6"
  }
  // ... 其他模型配置
}
```

> ⚠️ **安全提示**：
> - 不要将 `config.json` 提交到Git仓库
> - 项目已在 `.gitignore` 中排除此文件
> - 建议使用环境变量存储API密钥

**第3步：启用/禁用模型**

如果不想使用某个模型，可在 `arena.models` 中设置 `enabled: false`：

```json
{
  "arena": {
    "models": [
      {
        "name": "DeepSeek-V3.2",
        "provider": "deepseek",
        "enabled": false  // 禁用此模型
      }
    ]
  }
}
```

#### 5. 启动系统

**Windows（一键启动）**：
```powershell
.\start.ps1
```

**Linux/macOS（一键启动）**：
```bash
# 添加执行权限（首次运行）
chmod +x start.sh stop.sh

# 启动服务（后台运行）
./start.sh

# 查看日志
tail -f api.log        # 后端日志
tail -f frontend.log   # 前端日志
```

**功能说明**：
- ✅ 自动检测 Python 环境
- ✅ 后台启动后端（端口 8000）
- ✅ 后台启动前端（端口 8080）
- ✅ 自动打开浏览器
- ✅ 日志输出到文件
- ✅ 保存进程 PID 便于管理

**Linux/macOS（手动启动）**：

终端1 - 启动后端：
```bash
cd api
python3 -m uvicorn arena_api:app --host 0.0.0.0 --port 8000
```

终端2 - 启动前端：
```bash
python3 scripts/serve_frontend.py
```

**停止服务**：
- **Windows**: 关闭弹出的 PowerShell 窗口
- **Linux/macOS**: 
  ```bash
  ./stop.sh              # 一键停止所有服务
  # 或按 Ctrl+C（如在前台运行）
  ```

#### 6. 访问界面

浏览器打开：**http://localhost:8080**

### 📁 项目结构

```
LHArena/
├── api/                      # FastAPI后端
│   ├── main.py              # API主入口
│   └── routers/             # API路由
├── agent_v2/                # LangGraph Agent
│   └── langgraph_trading_agent.py  # 核心Agent逻辑
├── services/                # 服务层
│   ├── baostock_provider.py # Baostock数据服务
│   └── llm_provider.py      # AI模型服务
├── database/                # 数据库
│   ├── trade_manager.py     # 交易数据管理
│   └── trading.db           # SQLite数据库
├── frontend/                # 前端界面
│   ├── index.html           # 主页面
│   ├── echarts.min.js       # 图表库（本地）
│   └── tailwindcss-play.js  # 样式库（本地）
├── persistence/             # 数据持久化
│   └── *.pkl                # AI状态缓存
├── config.json              # 配置文件
├── requirements.txt         # Python依赖
├── start.ps1               # Windows启动脚本
├── start.sh                # Linux/macOS启动脚本
├── stop.sh                 # Linux/macOS停止脚本
└── README.md               # 本文档
```

### 📜 启动脚本说明

#### start.sh / start.ps1 - 一键启动脚本

**功能**：
- 检查 Python 环境（版本、路径）
- 自动启动后端 API 服务（FastAPI）
- 自动启动前端 HTTP 服务器
- 自动打开浏览器访问 http://localhost:8080
- 保存进程 PID 便于后续管理

**执行方式**：
- Windows: `.\start.ps1`（在独立窗口运行）
- Linux/macOS: `./start.sh`（后台运行）

**日志位置**：
- Windows: 在弹出窗口中显示
- Linux/macOS: `api.log` 和 `frontend.log`

#### stop.sh / stop.ps1 - 停止服务脚本

**功能**：
- 查找后端和前端进程
- 优雅地终止所有服务
- 清理 PID 文件

**执行方式**：
- Windows: `.\stop.ps1` 或直接关闭窗口
- Linux/macOS: `./stop.sh`

**强制停止**（如果脚本失败）：
```bash
# Windows
taskkill /F /IM python.exe

# Linux/macOS
pkill -f "arena_api"
pkill -f "serve_frontend"
```

### 🎯 使用说明

#### 启动竞技场

1. 打开浏览器访问 http://localhost:8080
2. 在界面中设置：
   - 回测开始日期（如：20250101）
   - 回测结束日期（如：20250331）
   - 启用的AI模型（默认全部启用）
3. 点击**"开始竞技"**按钮
4. 实时观看AI交易对决

#### 查看结果

- **排行榜**: 实时显示各AI的收益率、胜率排名
- **资金曲线**: 各AI的资金变化趋势
- **交易记录**: 详细的买入/卖出操作
- **持仓分析**: 当前各AI的持仓情况
- **AI思考**: 查看AI的决策理由和反思

#### 停止竞技

- 点击**"停止"**按钮
- 或关闭后端/前端服务窗口

### ⚙️ 配置说明

#### 交易参数

编辑 `config.json` 中的 `trading` 部分：

```json
{
  "trading": {
    "initial_capital": 10000,       // 初始资金（元）
    "max_price": 50,                // 股票最高价格限制
    "max_holdings": 999,            // 最大持仓数量
    "stop_loss_pct": 0.08,          // 止损比例（8%）
    "stop_profit_pct": 0.12,        // 止盈比例（12%）
    "target_hold_days": 5,          // 目标持仓天数
    "analyze_stock_count": 30,      // 每日分析股票数量
    "enable_reflection": true,      // 启用AI反思
    "reflection_interval": 5        // 反思间隔（天）
  }
}
```

#### 启用/禁用AI模型

编辑 `config.json` 中的 `arena.models`：

```json
{
  "arena": {
    "models": [
      {
        "name": "DeepSeek-V3.2",
        "provider": "deepseek",
        "enabled": true  // 改为 false 禁用此模型
      }
    ]
  }
}
```

### 🔧 技术架构

#### 后端架构

```
FastAPI
    ↓
Arena Manager (竞技场管理器)
    ↓
LangGraph Agent (状态机)
    ├─ 查找候选股票
    ├─ 分析卖出持仓
    ├─ 分析买入候选
    ├─ 执行卖出交易
    ├─ 执行买入交易
    └─ 自我反思优化
    ↓
Services
    ├─ BaostockProvider (数据)
    ├─ LLMProvider (AI调用)
    └─ TradeManager (交易管理)
```

#### AI决策流程

1. **市场扫描**: 获取符合条件的候选股票
2. **卖出分析**: AI分析当前持仓，决定是否卖出
3. **买入分析**: AI分析候选股票，选择最优标的
4. **风控检查**: 验证交易合规性（资金、仓位等）
5. **执行交易**: 记录交易到数据库
6. **定期反思**: AI总结经验，优化策略

### 📊 数据说明

#### Baostock数据

项目使用免费开源的Baostock数据源：
- 股票日线数据（价格、成交量、换手率等）
- 股票基本信息（代码、名称、行业等）
- 无需Token，完全免费
- 支持2015年至今的历史数据

#### 数据缓存

- 股票基本信息缓存在内存中
- 日线数据按需获取，减少重复请求
- 候选股票列表缓存，加速选股

### ⚠️ 注意事项

1. **API限制**
   - 各AI提供商有不同的调用限制
   - 建议先小范围测试（1-2个月）
   - 长时间回测建议单模型运行

2. **数据完整性**
   - Baostock数据可能有延迟（约15分钟）
   - 非交易日无法获取数据
   - 建议回测时间段至少距今1周以上

3. **性能考虑**
   - 5个AI同时运行较耗时
   - 长时间回测（1年+）可能需要数小时
   - 可关闭部分模型提升速度

4. **风险提示**
   - ⚠️ 本系统仅用于学习和研究
   - ⚠️ 回测结果不代表实盘表现
   - ⚠️ 实盘交易请充分评估风险

### 🛠️ 开发说明

#### 添加新的AI模型

1. 在 `config.json` 中添加模型配置
2. 在 `services/llm_provider.py` 中添加模型初始化
3. 在 `arena.models` 中注册模型

#### 自定义交易策略

编辑 `agent_v2/langgraph_trading_agent.py`：
- 修改 `_analyze_candidates()` 的AI Prompt
- 调整风控参数（止损止盈等）
- 添加新的技术指标

#### 扩展数据源

在 `services/` 中创建新的Provider：
```python
class NewDataProvider:
    def get_daily_price(self, ts_code, trade_date):
        # 实现数据获取逻辑
        pass
```

### 🐛 故障排查

#### 启动失败

```bash
# 检查端口占用
netstat -ano | findstr "8000"
netstat -ano | findstr "8080"

# 关闭占用进程
taskkill /PID <进程ID> /F
```

#### API调用失败

- 检查API密钥是否正确
- 确认网络可访问AI服务
- 查看后端日志输出

#### 数据获取失败

- 确认网络可访问Baostock
- 检查日期格式是否正确（YYYYMMDD）
- 查看是否为交易日

#### 前端无法访问

- 确认后端服务已启动（http://localhost:8000/docs）
- 检查浏览器控制台错误信息
- 清除浏览器缓存重试

### 📈 性能优化

1. **减少AI调用**
   - 减少 `analyze_stock_count`
   - 关闭不必要的AI模型
   - 增加 `reflection_interval`

2. **加速数据获取**
   - 数据已内置缓存机制
   - 避免重复回测相同时间段

3. **优化回测速度**
   - 先测试短时间（1个月）
   - 单模型运行更快
   - 使用更快的AI模型（如GLM-4.6）

### 📞 技术支持

- **Issues**: GitHub Issues
- **文档**: `te_docs/` 目录下的详细文档
- **日志**: 查看控制台输出和 `trading.db`

### 📄 许可证

MIT License

### 🙏 致谢

- [Baostock](http://baostock.com) - 提供免费A股数据
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent框架
- [FastAPI](https://fastapi.tiangolo.com) - Web框架
- [ECharts](https://echarts.apache.org) - 数据可视化

---

<a name="english"></a>
## 🇺🇸 English Documentation

### 📖 Introduction

AI Quantitative Trading Arena is an innovative multi-AI model competition platform that enables 5 top large language models (DeepSeek-V3.2, Qwen3-Max, GLM-4.6, Kimi-K2, Doubao-1.6) to compete in stock trading simultaneously. It uses LangGraph Agent architecture for intelligent decision-making and self-reflection, with real A-share historical data for backtesting.

### ✨ Key Features

- 🏆 **Multi-AI Competition**: 5 top AI models compete with real-time rankings
- 🧠 **Intelligent Decisions**: LangGraph-based Agent architecture with self-reflection
- 📊 **Real Data**: Integrated Baostock for complete A-share historical data
- 📈 **Live Visualization**: ECharts charts for capital curves, holdings, trade details
- 🎯 **Full Backtesting**: Support any time period from 2015 to present
- 💼 **Risk Control**: Built-in stop-loss/take-profit, position management
- 🔄 **Auto Reflection**: AI periodically reflects on decisions and optimizes strategies

### 🎮 Competing AI Models

| Model | Provider | Version | Features |
|-------|----------|---------|----------|
| DeepSeek-V3.2 | Alibaba Cloud | deepseek-v3.2-exp | Strong reasoning |
| Qwen3-Max | Alibaba Cloud | qwen3-max | Comprehensive |
| GLM-4.6 | Zhipu AI | glm-4.6 | Strong Chinese |
| Kimi-K2 | Moonshot AI | Moonshot-Kimi-K2-Instruct | Long context |
| Doubao-1.6 | ByteDance | doubao-seed-1-6-251015 | Innovative |

### 🚀 Quick Start

#### 1. Requirements

- **OS**: Windows 10/11, macOS, Linux
- **Python**: 3.10+ (Recommended 3.13.1)
- **RAM**: 8GB+ recommended
- **Network**: Access to AI APIs and Baostock

#### 2. Clone Repository

```bash
git clone https://github.com/gtd138/QuantArenaOSS.git
cd QuantArenaOSS
```

Or download and extract the source code directly.

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Main Dependencies**:
- `fastapi` - Backend API framework
- `uvicorn` - ASGI server
- `openai` - OpenAI-compatible AI model client
- `pandas` - Data processing and analysis
- `baostock` - Free A-share data source
- `langgraph` - LangChain Agent state machine framework
- `langchain` - AI application development framework
- `requests` - HTTP library
- `aiohttp` - Async HTTP client

#### 4. Configure API Keys

Edit `config.json` and fill in your API keys:

```json
{
  "deepseek": {
    "api_key": "your_alibaba_cloud_api_key",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "deepseek-v3.2-exp"
  }
  // ... other models
}
```

**Get API Keys**:
- Alibaba Cloud (DeepSeek/Qwen): https://dashscope.aliyuncs.com
- Zhipu AI (GLM): https://open.bigmodel.cn
- Moonshot AI (Kimi): https://platform.moonshot.cn
- Volcano Engine (Doubao): https://www.volcengine.com/product/doubao

#### 5. Start System

**Windows (One-Click)**:
```powershell
.\start.ps1
```

**Linux/macOS (One-Click)**:
```bash
# Add execute permission (first time only)
chmod +x start.sh stop.sh

# Start services (run in background)
./start.sh

# View logs
tail -f api.log        # Backend log
tail -f frontend.log   # Frontend log
```

**Features**:
- ✅ Auto-detect Python environment
- ✅ Start backend in background (port 8000)
- ✅ Start frontend in background (port 8080)
- ✅ Auto-open browser
- ✅ Log output to files
- ✅ Save process PIDs for management

**Linux/macOS (Manual)**:

Terminal 1 - Start Backend:
```bash
cd api
python3 -m uvicorn arena_api:app --host 0.0.0.0 --port 8000
```

Terminal 2 - Start Frontend:
```bash
python3 scripts/serve_frontend.py
```

**Stop Services**:
- **Windows**: Close PowerShell windows
- **Linux/macOS**: 
  ```bash
  ./stop.sh              # One-click stop all services
  # Or press Ctrl+C (if running in foreground)
  ```

#### 6. Access Interface

Open browser: **http://localhost:8080**

### 📁 Project Structure

```
LHArena/
├── api/                      # FastAPI Backend
│   ├── main.py              # API Entry
│   └── routers/             # API Routes
├── agent_v2/                # LangGraph Agent
│   └── langgraph_trading_agent.py  # Core Agent Logic
├── services/                # Service Layer
│   ├── baostock_provider.py # Baostock Data Service
│   └── llm_provider.py      # AI Model Service
├── database/                # Database
│   ├── trade_manager.py     # Trade Data Manager
│   └── trading.db           # SQLite Database
├── frontend/                # Frontend
│   ├── index.html           # Main Page
│   ├── echarts.min.js       # Charts (Local)
│   └── tailwindcss-play.js  # Styles (Local)
├── config.json              # Configuration
├── requirements.txt         # Python Dependencies
├── start.ps1               # Windows Startup Script
├── start.sh                # Linux/macOS Startup Script
├── stop.sh                 # Linux/macOS Stop Script
└── README.md               # This Document
```

### 📜 Startup Scripts Documentation

#### start.sh / start.ps1 - One-Click Startup Script

**Features**:
- Check Python environment (version, path)
- Auto-start backend API service (FastAPI)
- Auto-start frontend HTTP server
- Auto-open browser to http://localhost:8080
- Save process PIDs for management

**Execution**:
- Windows: `.\start.ps1` (runs in separate windows)
- Linux/macOS: `./start.sh` (runs in background)

**Log Location**:
- Windows: Displayed in popup windows
- Linux/macOS: `api.log` and `frontend.log`

#### stop.sh / stop.ps1 - Stop Services Script

**Features**:
- Find backend and frontend processes
- Gracefully terminate all services
- Clean up PID files

**Execution**:
- Windows: `.\stop.ps1` or close windows
- Linux/macOS: `./stop.sh`

**Force Stop** (if script fails):
```bash
# Windows
taskkill /F /IM python.exe

# Linux/macOS
pkill -f "arena_api"
pkill -f "serve_frontend"
```

### 🎯 Usage

#### Start Arena

1. Open browser: http://localhost:8080
2. Set parameters:
   - Backtest start date (e.g., 20250101)
   - Backtest end date (e.g., 20250331)
   - Enable AI models (all enabled by default)
3. Click **"Start Competition"**
4. Watch live AI trading battle

#### View Results

- **Leaderboard**: Real-time ROI and win rate rankings
- **Capital Curves**: Asset trends for each AI
- **Trade Records**: Detailed buy/sell operations
- **Holdings Analysis**: Current positions of each AI
- **AI Thinking**: View AI decision reasons and reflections

### ⚙️ Configuration

#### Trading Parameters

Edit `trading` section in `config.json`:

```json
{
  "trading": {
    "initial_capital": 10000,       // Initial capital (CNY)
    "max_price": 50,                // Max stock price limit
    "stop_loss_pct": 0.08,          // Stop loss (8%)
    "stop_profit_pct": 0.12,        // Take profit (12%)
    "enable_reflection": true,      // Enable AI reflection
    "reflection_interval": 5        // Reflection interval (days)
  }
}
```

### 🔧 Architecture

#### Backend Architecture

```
FastAPI → Arena Manager → LangGraph Agent → Services
```

#### AI Decision Flow

1. **Market Scan**: Get qualified candidate stocks
2. **Sell Analysis**: AI analyzes holdings, decides whether to sell
3. **Buy Analysis**: AI analyzes candidates, selects optimal targets
4. **Risk Check**: Validate trade compliance
5. **Execute Trade**: Record to database
6. **Periodic Reflection**: AI summarizes and optimizes strategy

### ⚠️ Cautions

1. **API Limits**: Different providers have different rate limits
2. **Data Integrity**: Baostock has ~15min delay
3. **Performance**: 5 AIs running simultaneously is time-consuming
4. **Risk Warning**: ⚠️ For research only, not investment advice

### 📄 License

MIT License

### 🙏 Credits

- [Baostock](http://baostock.com) - Free A-share data
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent framework
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
- [ECharts](https://echarts.apache.org) - Data visualization

---

**Version**: 2.0.0  
**Tech Stack**: Python + FastAPI + LangGraph + Baostock + AI Models  
**Last Updated**: 2025-10-29

---

<div align="center">

![QuantArenaOSS](https://raw.githubusercontent.com/gtd138/QuantArenaOSS/main/QuantArenaOSS.png)

</div>
