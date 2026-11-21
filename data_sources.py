#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源接口管理中心 (data_sources.py)
100% 映射源项目 zadescoxp/order-flow-screener 的全部 12 大市场数据源适配器与环境变量：
- 加密货币永续合约 (6家): Binance Futures (USD-M /market/ws & /public/ws + 1000档REST), Bybit Futures (orderbook.1000),
  OKX Futures (books 400档), Bitget Futures (全量增量订单簿), Hyperliquid (activeAssetCtx), Deribit (BTC/ETH 币本位永续)
- 加密货币现货 (5家): Binance Spot, Bybit Spot, OKX Spot, Bitget Spot, Coinbase Spot (level2 全量簿)
- 外汇与贵金属市场 (1家): Finnhub (OANDA 命名空间, EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD 等 20 货币对, NEXT_PUBLIC_FINNHUB_API_KEY)
支持可视化配置、.env.local 双向持久化、连通性延迟测试与完整能力矩阵查询。
"""

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional


CONFIG_DIR = Path.home() / ".order_flow_screener"
DS_CONFIG_FILE = CONFIG_DIR / "data_sources.json"


# 源项目完整支持品种目录 (29+ 核心 USDT 加密货币 + 黄金/白银永续 + 20 FX 外汇对)
CRYPTO_INSTRUMENTS: List[str] = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT",
    "TRXUSDT", "ADAUSDT", "HYPEUSDT", "LINKUSDT", "SUIUSDT", "AVAXUSDT",
    "BCHUSDT", "LTCUSDT", "DOTUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT",
    "AAVEUSDT", "ETCUSDT", "ENAUSDT", "ATOMUSDT", "ARBUSDT", "OPUSDT",
    "INJUSDT", "FILUSDT", "SEIUSDT", "TIAUSDT", "WIFUSDT", "XAUUSDT", "XAGUSDT"
]

FOREX_INSTRUMENTS: List[str] = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "USD/CHF", "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY",
    "AUD/JPY", "EUR/AUD", "EUR/CAD", "GBP/AUD", "CHF/JPY",
    "CAD/JPY", "NZD/JPY", "GBP/CAD", "GBP/CHF", "AUD/CAD"
]


DEFAULT_DATA_SOURCES: Dict[str, Dict[str, Any]] = {
    "binance_futures": {
        "id": "binance_futures",
        "name": "Binance Futures (币安 U本位永续)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BINANCE_FUTURES_API_KEY",
        "ws_endpoint": "wss://fstream.binance.com/market/ws",
        "rest_endpoint": "https://fapi.binance.com/fapi/v1/time",
        "depth_reach": "实时 Top 20 + 每5秒 1000档 REST 快照 + 前日5m K线 (pPOC/nPOC)",
        "capabilities": ["逐笔成交 (aggTrade)", "订单簿深度 (1000档)", "持仓量 (REST 5s)", "资金费率/标记价 (markPrice)", "强平爆仓流 (forceOrder)", "前日关键位与7日裸POC"],
    },
    "bybit_futures": {
        "id": "bybit_futures",
        "name": "Bybit Futures (Bybit 永续合约)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BYBIT_API_KEY",
        "ws_endpoint": "wss://stream.bybit.com/v5/public/linear",
        "rest_endpoint": "https://api.bybit.com/v5/market/time",
        "depth_reach": "orderbook.1000 (1000档全量深度)",
        "capabilities": ["逐笔成交 (publicTrade)", "订单簿深度 (1000档)", "持仓量与资金费率 (tickers)", "全量爆仓流 (allLiquidation)"],
    },
    "okx_futures": {
        "id": "okx_futures",
        "name": "OKX Futures (欧易永续合约)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "OKX_API_KEY",
        "ws_endpoint": "wss://ws.okx.com:8443/ws/v5/public",
        "rest_endpoint": "https://www.okx.com/api/v5/public/time",
        "depth_reach": "books (400档深度)",
        "capabilities": ["逐笔成交 (trades)", "订单簿深度 (400档)", "持仓量 (open-interest)", "资金费率 (funding-rate)", "标记/指数价", "爆仓订单流 (liquidation-orders)"],
    },
    "bitget_futures": {
        "id": "bitget_futures",
        "name": "Bitget Futures (Bitget 永续合约)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BITGET_API_KEY",
        "ws_endpoint": "wss://ws.bitget.com/v2/ws/public",
        "rest_endpoint": "https://api.bitget.com/api/v2/public/time",
        "depth_reach": "books (全量增量订单簿)",
        "capabilities": ["逐笔成交", "全量增量订单簿", "持仓量与资金费率 (ticker)"],
    },
    "hyperliquid": {
        "id": "hyperliquid",
        "name": "Hyperliquid (去中心化永续 L1)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "HYPERLIQUID_API_KEY",
        "ws_endpoint": "wss://api.hyperliquid.xyz/ws",
        "rest_endpoint": "https://api.hyperliquid.xyz/info",
        "depth_reach": "20 - 50 档 L2 Book",
        "capabilities": ["逐笔成交 (HYPE及主流币)", "L2 订单簿", "实时持仓与每小时资金费率 (activeAssetCtx)", "Oracle 预言机基差"],
    },
    "deribit": {
        "id": "deribit",
        "name": "Deribit (BTC/ETH 机构级衍生品)",
        "category": "加密货币永续 (Crypto Perp)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "DERIBIT_API_KEY",
        "ws_endpoint": "wss://www.deribit.com/ws/api/v2",
        "rest_endpoint": "https://www.deribit.com/api/v2/public/get_time",
        "depth_reach": "20 - 50 档深度 (支持 BTC/ETH 币本位永续)",
        "capabilities": ["BTC/ETH 逐笔成交 (含内嵌爆仓标记)", "订单簿深度", "USD 折算持仓量", "8小时资金费率 (funding_8h)"],
    },
    "binance_spot": {
        "id": "binance_spot",
        "name": "Binance Spot (币安现货)",
        "category": "加密货币现货 (Crypto Spot)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BINANCE_SPOT_API_KEY",
        "ws_endpoint": "wss://stream.binance.com:9443/ws",
        "rest_endpoint": "https://api.binance.com/api/v3/time",
        "depth_reach": "20 - 50 档现货深度 + 5m 历史 K线",
        "capabilities": ["现货逐笔成交", "现货订单簿", "前日现货 POC/VAH/VAL/VWAP 关键位"],
    },
    "bybit_spot": {
        "id": "bybit_spot",
        "name": "Bybit Spot (Bybit 现货)",
        "category": "加密货币现货 (Crypto Spot)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BYBIT_SPOT_API_KEY",
        "ws_endpoint": "wss://stream.bybit.com/v5/public/spot",
        "rest_endpoint": "https://api.bybit.com/v5/market/time",
        "depth_reach": "orderbook.200 现货深度",
        "capabilities": ["现货逐笔成交", "现货订单簿深度", "跨所现货价差对比"],
    },
    "okx_spot": {
        "id": "okx_spot",
        "name": "OKX Spot (欧易现货)",
        "category": "加密货币现货 (Crypto Spot)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "OKX_SPOT_API_KEY",
        "ws_endpoint": "wss://ws.okx.com:8443/ws/v5/public",
        "rest_endpoint": "https://www.okx.com/api/v5/public/time",
        "depth_reach": "books (400档现货深度)",
        "capabilities": ["现货逐笔成交", "400档现货订单簿", "冰山单补单检测"],
    },
    "bitget_spot": {
        "id": "bitget_spot",
        "name": "Bitget Spot (Bitget 现货)",
        "category": "加密货币现货 (Crypto Spot)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "BITGET_SPOT_API_KEY",
        "ws_endpoint": "wss://ws.bitget.com/v2/ws/public",
        "rest_endpoint": "https://api.bitget.com/api/v2/public/time",
        "depth_reach": "books (全量增量现货订单簿)",
        "capabilities": ["现货逐笔成交", "全量增量现货深度"],
    },
    "coinbase_spot": {
        "id": "coinbase_spot",
        "name": "Coinbase Spot (Coinbase 美元现货)",
        "category": "加密货币现货 (Crypto Spot)",
        "enabled": True,
        "requires_key": False,
        "api_key": "",
        "env_key": "COINBASE_API_KEY",
        "ws_endpoint": "wss://ws-feed.exchange.coinbase.com",
        "rest_endpoint": "https://api.exchange.coinbase.com/time",
        "depth_reach": "level2 (全量 L2 订单簿，除 TRX 外全覆盖)",
        "capabilities": ["USD 机构现货成交流", "全量 L2 挂单热力图采样", "跨所 Lead/Lag 领涨风向标"],
    },
    "finnhub_forex": {
        "id": "finnhub_forex",
        "name": "Finnhub Forex (OANDA 外汇实时流)",
        "category": "外汇市场 (Forex / OANDA)",
        "enabled": True,
        "requires_key": True,
        "api_key": "",
        "env_key": "NEXT_PUBLIC_FINNHUB_API_KEY",
        "ws_endpoint": "wss://ws.finnhub.io",
        "rest_endpoint": "https://finnhub.io/api/v1/forex/rates?base=USD",
        "depth_reach": "Tick 价格方向分类 + 响应式买卖报价代理 (Quote Proxy OBI)",
        "capabilities": ["OANDA:EUR_USD 等 20 货币对实时 Tick", "Tick Volume Z-Score 异常活跃度", "纽约交易时段 (周日17:00-周五17:00) 自动门控"],
    },
}


class DataSourceManager:
    """管理所有加密货币与外汇数据源、环境变量同步 (.env.local) 及连通性健康检查"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.config_path = DS_CONFIG_FILE
        self.sources: Dict[str, Dict[str, Any]] = json.loads(json.dumps(DEFAULT_DATA_SOURCES))
        self.site_url: str = "http://localhost:3000"
        self.proxy_url: str = ""
        self.load_config()

    def load_config(self) -> None:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.site_url = data.get("site_url", self.site_url)
                self.proxy_url = data.get("proxy_url", self.proxy_url)
                saved = data.get("sources", {})
                for sid, scfg in saved.items():
                    if sid in self.sources:
                        self.sources[sid].update(scfg)
            except Exception:
                pass

        # 同步读取工程目录下 .env.local (与原 Next.js / 终端配置保持 100% 互通)
        env_local = self.project_root / ".env.local"
        if env_local.exists():
            try:
                for line in env_local.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k == "NEXT_PUBLIC_FINNHUB_API_KEY" and v:
                        self.sources["finnhub_forex"]["api_key"] = v
                    elif k == "NEXT_PUBLIC_SITE_URL" and v:
                        self.site_url = v
            except Exception:
                pass

    def save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "site_url": self.site_url,
            "proxy_url": self.proxy_url,
            "sources": self.sources,
        }
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._sync_env_local()

    def _sync_env_local(self) -> None:
        """同步写入 .env.local，确保原版配置与桌面终端完全一致"""
        try:
            env_local = self.project_root / ".env.local"
            finnhub_key = self.sources.get("finnhub_forex", {}).get("api_key", "")
            lines = [
                "# Order Flow Screener (中文桌面版) 自动生成环境配置文件",
                f"NEXT_PUBLIC_FINNHUB_API_KEY={finnhub_key}",
                f"NEXT_PUBLIC_SITE_URL={self.site_url}",
            ]
            if self.proxy_url:
                lines.append(f"HTTP_PROXY={self.proxy_url}")
                lines.append(f"HTTPS_PROXY={self.proxy_url}")
            for sid, scfg in self.sources.items():
                env_k = scfg.get("env_key")
                val = scfg.get("api_key", "")
                if env_k and env_k != "NEXT_PUBLIC_FINNHUB_API_KEY" and val:
                    lines.append(f"{env_k}={val}")
            env_local.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    def update_source(self, source_id: str, enabled: bool, api_key: str = "") -> None:
        if source_id in self.sources:
            self.sources[source_id]["enabled"] = bool(enabled)
            self.sources[source_id]["api_key"] = api_key.strip()
            self.save_config()

    def test_connectivity(self, source_id: str) -> Dict[str, Any]:
        """探测指定交易所或 Finnhub 数据源的 REST/WS 网关延迟与可用状态"""
        scfg = self.sources.get(source_id)
        if not scfg:
            return {"ok": False, "source_id": source_id, "latency_ms": 0, "message": "未知数据源"}

        if scfg.get("requires_key") and not scfg.get("api_key"):
            return {
                "ok": False,
                "source_id": source_id,
                "latency_ms": 0,
                "message": "需配置 NEXT_PUBLIC_FINNHUB_API_KEY 后方可启用外汇实时流",
            }

        url = scfg.get("rest_endpoint", "")
        if source_id == "finnhub_forex" and scfg.get("api_key"):
            url = f"{url}&token={scfg['api_key']}"

        t0 = time.time()
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "OrderFlowScreener-CN/2.3.0"},
                method="GET" if source_id != "hyperliquid" else "POST",
                data=b'{"type":"meta"}' if source_id == "hyperliquid" else None,
            )
            if source_id == "hyperliquid":
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                latency = int((time.time() - t0) * 1000)
                return {
                    "ok": resp.status == 200,
                    "source_id": source_id,
                    "latency_ms": latency,
                    "message": f"网关在线 ({latency} ms) | {scfg.get('depth_reach')}",
                }
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            return {
                "ok": False,
                "source_id": source_id,
                "latency_ms": latency,
                "message": f"离线或需代理 ({latency} ms): {str(e)[:60]}",
            }
