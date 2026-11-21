# Order Flow Screener 订单流微观结构量化终端 v2.3.0 (全中文原生 PySide6 桌面安装版)

本项目基于上游开源仓库 [zadescoxp/order-flow-screener](https://github.com/zadescoxp/order-flow-screener) (Order Flow Tracker v2.3.0)，严格按照您的 EXE 打包、自动更新与全中文本地化规范进行重构与增强，发布为标准 Windows 安装程序 `OrderFlowScreener-Setup-win64.exe`。

## 一、 核心架构与记忆规范对齐清单

| 规范维度 | 实现方案与对应模块 |
| :--- | :--- |
| **纯原生中文桌面 GUI** | `gui_app.py`：采用 **PySide6 (Qt 6)** 现代深色卡片布局 + 微软雅黑字体，启用 Per-Monitor v2 HiDPI 感知与 `PassThrough` 缩放策略，完全摒弃 Web 套壳或 Tkinter |
| **无黑框与后台静默** | `launcher.py` + `updater.py`：PyInstaller `--noconsole` 编译，所有后台子进程统一附加 `CREATE_NO_WINDOW (0x08000000)`，日志自动落盘至 `~/.order_flow_screener/app.log` |
| **256px 高清图标与托盘** | `scripts/generate_icon.py`：自动生成含 `256/128/64/48/32/16px` 的 `app_icon_v230.ico`，运行时绑定 `AppUserModelID` 与 Win32 `WM_SETICON`，并支持 `QSystemTrayIcon` 最小化至系统托盘常驻 |
| **标准 Inno Setup 安装包** | `installer/order-flow-screener.iss`：严禁 `--onefile` 单文件便携版，仅打包 PyInstaller `--onedir` 精简目录（剔除冗余 QtWebEngine/Qt3D/QtQuick）为 `OrderFlowScreener-Setup-win64.exe` (`WizardStyle=modern`, `ChangesAssociations=yes`) |
| **免 Key 本地与云端大模型** | `llm_providers.py` + `local_api_server.py`：支持 **Ollama (`11434`)**、**LM Studio (`1234`)**、**vLLM (`8000`)** 免 Key 直连与本地模型自动发现；集成 DeepSeek、硅基流动、通义千问、智谱 GLM、月之暗面 Kimi、OpenAI、Gemini、Claude；同时在本地后台启动 `http://127.0.0.1:8787` OpenAI 兼容 API 服务 |
| **12 大数据源接口中心** | `data_sources.py`：完整纳管 6 家加密货币永续（Binance / Bybit / OKX / Bitget / Hyperliquid / Deribit）、5 家加密货币现货（含 Coinbase Spot L2）及 Finnhub (`OANDA` 外汇 20 货币对)，支持双向同步 `.env.local` 与并发延迟探测 |
| **自动更新与上游同步** | `updater.py` + `.github/workflows/release-exe.yml`：应用内一键检查 GitHub Releases 并支持 `/VERYSILENT` 静默覆盖升级；GitHub Actions 每日自动同步上游 `zadescoxp/order-flow-screener`，执行 `--mode self-test` 自检后发布最新安装包 |

## 二、 源项目 100% 功能汉化与原生面板映射

1. **📊 1. 足迹图与热力图主终端**：
   - 连续 Tick 阶梯足迹图（`买×卖双列 Bid×Ask`、`净差值 Delta`、`成交总量 Volume` 三模式切换）
   - 单价位对角失衡高亮（`≥3×`）与连续堆叠失衡区（`Stacked Imbalances ≥3档`）
   - 单 K 线 POC 金框、当日 70% 价值区（`Session POC / VAH / VAL`）与 `VWAP ±1σ/±2σ` 轨迹线
   - 挂单流动性深度热力图（`Resting-Liquidity Heatmap`）与成交量热力图叠加
   - 被动限价吸收标记（`ABS`）与机构冰山单补单检测（`Iceberg` 冰蓝圆点）、大单气泡与强平爆仓圆环
   - 多所聚合订单簿阶梯（`Order Book Ladder`）、`OBI` 买卖失衡度进度条、毫秒级逐笔成交流（`Time & Sales`）与双轴 `CVD vs 价格` 背离副图
2. **🌐 2. 跨所领涨对比与前日/裸 POC**：
   - 跨交易所基点价差（`bps`）、1 分钟成交份额、1 分钟净 Delta、以及 `250ms` 步进（`±2000ms`）价格变化互相关领涨交易所识别（`Lead / Lag`）
   - 前一交易日关键位（`pPOC / pVAH / pVAL / pVWAP`）与近 7 日未回补裸 POC（`nPOC MM/DD`）
3. **⚡ 3. 衍生品持仓四象限与强平爆仓**：
   - 全网聚合持仓量（`Open Interest`）四象限状态机：`新多入场 (价升仓增)`、`空头回补 (价升仓减)`、`新空入场 (价跌仓增)`、`多头平仓 (价跌仓减)`
   - OI 加权 8 小时资金费率（`Funding`）、标记/指数期现基差（`Basis`）、分桶多空强平爆仓级联（`Cascade`）及年化已实现波动率（`RV / ATR(14) / Parkinson`）
4. **🔔 4. 智能预警・录制回放・数据导出**：
   - 9 大微观结构智能预警规则开关与实时触发日志
   - 实时市场流分块录制（`Rec`）与 `1× / 5× / 20×` 虚拟时钟回放
   - 一键导出原版兼容格式足迹图 `CSV`、高清画布快照 `PNG` 及 `Markdown / HTML` 量化诊断报告

## 三、 快速发布与本地构建指南

### 方式 A：使用一键自动化脚本推送至您的 GitHub 并触发云端打包（推荐）
在 Windows PowerShell 中解压工程包后运行：
```powershell
.\deploy_to_github.ps1
```
脚本将自动把 `zadescoxp/order-flow-screener` Fork 到您的 `gouqizi2214730-source/order-flow-screener` 仓库，推送全套中文桌面代码，并触发 GitHub Actions 云端自动完成 `--mode self-test` 自检与 `OrderFlowScreener-Setup-win64.exe` 安装包发布。

### 方式 B：在本地 Windows 环境直接编译安装包
```powershell
pip install -r requirements-desktop.txt
python scripts/generate_icon.py
python launcher.py --mode self-test
pyinstaller --noconfirm --clean --onedir --noconsole --name "OrderFlowScreener" --icon "app_icon_v230.ico" --add-data "app_icon_v230.ico;." --add-data "scripts;scripts" launcher.py
iscc installer/order-flow-screener.iss
```
编译完成后，标准安装包位于 `dist\OrderFlowScreener-Setup-win64.exe`。
