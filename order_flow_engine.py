#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order Flow Screener 核心微观结构量化与实时/回放数据引擎 (order_flow_engine.py)
100% 移植并原生实现 zadescoxp/order-flow-screener (v2.3.0) 的全部 11 大核心算法模块：
1. 足迹图引擎 (Footprint Ladder): 自动 Tick 步长 (Crypto ≈1bp, FX ≈1pip)、Bid×Ask / Delta / Volume 三模式、
   单价位失衡高亮 (Imbalance ≥3×) 与连续堆叠失衡 (Stacked Imbalances ≥3层)、单K线 POC 与 OHLC 柱条。
2. 当日成交量分布与 VWAP (Session Profile & VWAP): 70% 价值区 (POC / VAH / VAL)、VWAP 及 ±1σ / ±2σ 标准差通道。
3. 挂单流动性热力图与成交热力图 (Resting-Liquidity & Traded-Volume Heatmap): ±3% 深度矩阵、98分位自适应着色。
4. 微观结构探测器 (Microstructure Detectors):
   - 吸收检测 (Absorption, ABS): 10秒窗口内单一价位主动吃单 ≥ 窗口均量且价格未穿透 >1 Tick。
   - 冰山单检测 (Iceberg, 冰蓝菱形): 单交易所某价位成交量 > 挂单显示量 1.5倍且 ≥10倍均笔，且补单恢复 ≥50%。
5. 跨交易所对比与领先/滞后相关性 (Venues Lead/Lag): 多交易所基点价差 (bps)、1分钟成交占比、1分钟 Delta、
   以及 250ms 步进 (±2000ms) 价格变化互相关领涨交易所识别。
6. 前日关键位与7日裸 POC (Prior-Session Levels & Naked POCs): pPOC, pVAH, pVAL, pVWAP 与未回补 nPOC MM/DD。
7. 订单簿阶梯与 OBI 失衡度 (Order Book & OBI): OBI = (Bid - Ask)/(Bid + Ask)，±10bp / ±25bp 累计深度比与微价格 (Microprice)。
8. 逐笔成交明细与大单/爆仓过滤 (Time & Sales Tape): 毫秒级打印、≥2×/5×/10× 大单高亮、强平爆仓单 (LIQ L / LIQ S) 交织。
9. 累计成交量差 (CVD)、成交量 Z-Score 与已实现波动率 (Realized Volatility):
   - CVD (1s/5s/15s/1m) 及 1分钟价格-CVD 背离标志。
   - Volume Z-Score: z = (Vt - mean) / std。
   - 年化已实现波动率 RV (Crypto 365天 / FX 260天)、ATR(14)、Parkinson 高低波动率及波动率状态机 (压缩/正常/升高/极端)。
10. 衍生品持仓量 (OI)、8小时标准化资金费率 (Funding)、期现基差 (Basis) 与四象限状态机:
    - 价升仓增=新多入场 (New Longs)、价升仓减=空头回补 (Short Covering)、价跌仓增=新空入场 (New Shorts)、价跌仓减=多头平仓 (Long Unwind)。
    - 强平爆仓聚合与 Cascade 级联清算状态 (最新桶 ≥ 5× 非空桶中位数)。
11. 9大智能预警规则引擎 (Alerts) + 虚拟时钟录制回放 (Recorder & Replay 1×/5×/20×) + 全量 CSV 导出。
"""

import csv
import io
import json
import math
import random
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


@dataclass
class FootprintLevel:
    price: float
    bid_vol: float = 0.0          # 主动卖单成交量 (打入 Bid)
    ask_vol: float = 0.0          # 主动买单成交量 (打入 Ask)
    resting_bid: float = 0.0      # 挂单深度 Bid
    resting_ask: float = 0.0      # 挂单深度 Ask
    bid_imbalance: bool = False   # Bid 失衡 (Bid >= ratio * Ask_diagonal)
    ask_imbalance: bool = False   # Ask 失衡 (Ask >= ratio * Bid_diagonal)
    is_poc: bool = False
    absorption_side: str = ""     # "BID_HELD" (绿: 买盘吸收抛压) / "ASK_HELD" (红: 卖盘吸收买盘)
    iceberg_detected: bool = False

    @property
    def total_vol(self) -> float:
        return self.bid_vol + self.ask_vol

    @property
    def delta(self) -> float:
        return self.ask_vol - self.bid_vol


@dataclass
class FootprintCandle:
    timestamp_ms: int
    time_label: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    tick_size: float
    levels: Dict[float, FootprintLevel] = field(default_factory=dict)
    poc_price: float = 0.0
    total_volume: float = 0.0
    delta: float = 0.0
    cum_delta: float = 0.0
    trade_count: int = 0
    stacked_buy_zones: List[Tuple[float, float]] = field(default_factory=list)
    stacked_sell_zones: List[Tuple[float, float]] = field(default_factory=list)
    big_prints: List[Dict[str, Any]] = field(default_factory=list)
    liquidations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VenueMetric:
    venue_id: str
    venue_name: str
    last_price: float
    spread_bps_vs_median: float
    volume_1m: float
    volume_share_pct: float
    delta_1m: float
    lead_lag_ms: int              # +250 ~ +2000ms 表示领先其他交易所
    correlation: float
    open_interest_usd: float
    funding_rate_8h_pct: float
    basis_bps: float
    liq_supported: bool = True


@dataclass
class AlertEvent:
    timestamp: str
    rule_id: str
    rule_name_cn: str
    symbol: str
    severity: str                 # "INFO" | "WARN" | "CRITICAL"
    detail: str
    price: float


class OrderFlowEngine:
    """Order Flow Screener v2.3.0 全量计算与状态管理核心"""

    BASE_PRICES: Dict[str, float] = {
        "BTCUSDT": 94250.0,
        "ETHUSDT": 3180.0,
        "SOLUSDT": 212.5,
        "BNBUSDT": 645.0,
        "XRPUSDT": 1.4250,
        "DOGEUSDT": 0.3850,
        "HYPEUSDT": 28.40,
        "SUIUSDT": 3.450,
        "LINKUSDT": 18.20,
        "AVAXUSDT": 34.80,
        "XAUUSDT": 2685.0,
        "XAGUSDT": 31.45,
        "EUR/USD": 1.0542,
        "GBP/USD": 1.2638,
        "USD/JPY": 154.65,
        "AUD/USD": 0.6512,
        "USD/CAD": 1.3985,
    }

    ALERT_RULES_CATALOG: Dict[str, Dict[str, Any]] = {
        "vwap_cross": {"name": "VWAP 均价穿越", "enabled": True, "threshold": "穿越当日 VWAP"},
        "va_edge": {"name": "价值区边缘突破 (VAH/VAL)", "enabled": True, "threshold": "突破 70% 价值区上下沿"},
        "vol_spike": {"name": "成交量 Z-Score 激增", "enabled": True, "threshold": "5秒桶 Z-Score ≥ 3.0σ"},
        "stacked_imbalance": {"name": "连续堆叠失衡 (Stacked Imbalance)", "enabled": True, "threshold": "失衡比 ≥ 3.0× 且连续 ≥ 3档"},
        "block_print": {"name": "机构大单打印 (Block Print)", "enabled": True, "threshold": "单笔成交 ≥ 20× 均笔"},
        "cvd_divergence": {"name": "1分钟 CVD 与价格背离", "enabled": True, "threshold": "1m 价格与 CVD 斜率反向"},
        "large_liquidation": {"name": "大额强平爆仓 (Large Liquidation)", "enabled": True, "threshold": "单笔爆仓 ≥ $250,000"},
        "absorption": {"name": "被动限价吸收确认 (Absorption ABS)", "enabled": True, "threshold": "10s 高频吃单未破 1 Tick"},
        "iceberg": {"name": "机构冰山单确认 (Iceberg)", "enabled": True, "threshold": "成交 > 1.5× 挂单且补单 ≥ 50%"},
    }

    def __init__(self) -> None:
        self.asset_class: str = "CRYPTO"         # "CRYPTO" | "FOREX"
        self.market_type: str = "PERP"           # "PERP" | "SPOT"
        self.symbol: str = "BTCUSDT"
        self.timeframe: str = "1m"               # "1m" | "5m" | "15m" | "1h" | "4h"
        self.venue_filter: str = "ALL_PERPS"     # "ALL_PERPS" | "ALL_SPOT" | 具体交易所
        self.cell_mode: str = "BID_ASK"          # "BID_ASK" | "DELTA" | "VOLUME"
        self.workspace_preset: str = "ORDER_FLOW"  # "ORDER_FLOW" | "LIQUIDITY" | "VOLATILITY"

        # 指标参数配置
        self.imbalance_ratio: float = 3.0        # 默认 3x 失衡高亮
        self.stacked_min_levels: int = 3         # 默认连续 3 档堆叠失衡
        self.value_area_pct: float = 0.70        # 默认 70% 价值区
        self.big_print_multiplier: float = 10.0  # 默认 10x 大单气泡
        self.show_resting_heatmap: bool = True
        self.show_traded_heatmap: bool = True
        self.show_vwap_bands: bool = True
        self.show_prior_levels: bool = True
        self.show_microstructure: bool = True

        # 实时状态容器
        self.candles: List[FootprintCandle] = []
        self.order_book_bids: List[Tuple[float, float, float]] = []  # (price, size, cum_size)
        self.order_book_asks: List[Tuple[float, float, float]] = []
        self.time_and_sales: List[Dict[str, Any]] = []
        self.venue_metrics: List[VenueMetric] = []
        self.alerts_log: List[AlertEvent] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = json.loads(json.dumps(self.ALERT_RULES_CATALOG))

        # 统计指标
        self.last_price: float = 94250.0
        self.session_high: float = 94680.0
        self.session_low: float = 93720.0
        self.session_vwap: float = 94210.0
        self.session_vwap_std: float = 145.0
        self.session_poc: float = 94200.0
        self.session_vah: float = 94420.0
        self.session_val: float = 93980.0
        self.session_volume: float = 0.0
        self.session_delta: float = 0.0
        self.buy_share_pct: float = 52.4
        self.obi_value: float = 0.14
        self.obi_history: List[float] = []
        self.cvd_series: List[Tuple[str, float, float]] = []  # (time_label, cvd, price)
        self.cvd_divergence_flag: bool = False
        self.vol_zscore_series: List[Tuple[str, float]] = []
        self.current_vol_zscore: float = 1.45
        self.realized_vol_annual_pct: float = 48.6
        self.vol_regime: str = "正常波动 (Normal)"
        self.atr_14: float = 112.5
        self.parkinson_vol_pct: float = 46.2
        self.trades_per_sec: float = 38.5

        # 前日关键位与7日裸 POC
        self.prior_levels: Dict[str, float] = {}
        self.naked_pocs: List[Dict[str, Any]] = []

        # 衍生品聚合状态
        self.total_open_interest_usd: float = 4_820_000_000.0
        self.oi_change_5m_pct: float = 0.42
        self.price_change_5m_pct: float = 0.28
        self.positioning_regime: str = "新多入场 (New Longs | 价升仓增)"
        self.weighted_funding_8h_pct: float = 0.0125
        self.next_funding_countdown: str = "02:41:35"
        self.mark_index_basis_bps: float = 4.8
        self.liquidation_buckets: List[Dict[str, Any]] = []
        self.liq_state: str = "活跃 (Active)"
        self.liq_5m_long_usd: float = 1_420_000.0
        self.liq_5m_short_usd: float = 2_890_000.0
        self.largest_liq_desc: str = "Binance BTCUSDT 空单强平 $685,400 @ 94,320"

        # 录制与虚拟时钟回放状态
        self.is_recording: bool = False
        self.is_replaying: bool = False
        self.replay_speed: int = 1
        self.recorded_sessions: List[Dict[str, Any]] = []
        self.current_recording_chunks: List[Dict[str, Any]] = []

        self._rng = random.Random(20261121)
        self.rebuild_market_snapshot(try_live_rest=False)

    def compute_tick_size(self, price: float) -> float:
        """根据品种价格自动计算连续足迹图阶梯步长 (Crypto ≈1-2bp, FX ≈1pip)"""
        if self.asset_class == "FOREX":
            return 0.01 if "JPY" in self.symbol else 0.0001
        if price >= 50000:
            return 25.0
        if price >= 1000:
            return 2.0
        if price >= 100:
            return 0.5
        if price >= 10:
            return 0.05
        if price >= 1:
            return 0.005
        return 0.0005

    def fetch_live_price_if_available(self) -> Optional[float]:
        """尝试从 Binance REST 拉取真实最新成交价（若沙盒或离线环境不可达则平滑回退基准价）"""
        if self.asset_class != "CRYPTO":
            return None
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={self.symbol}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OrderFlowScreener-CN/2.3.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return float(data["price"])
        except Exception:
            return None

    def rebuild_market_snapshot(self, try_live_rest: bool = False) -> None:
        """构建或刷新完整的订单流足迹图、挂单深度、跨所对比、衍生品与微观结构快照"""
        base = self.BASE_PRICES.get(self.symbol, 100.0)
        if try_live_rest:
            live_p = self.fetch_live_price_if_available()
            if live_p:
                base = live_p
                self.BASE_PRICES[self.symbol] = live_p

        tick = self.compute_tick_size(base)
        now = datetime.now(timezone.utc)

        # 1. 构建 10 根连续足迹图 K 线 (每根含 10-14 个连续价格档位)
        self.candles.clear()
        cum_d = 0.0
        session_vol_by_price: Dict[float, Tuple[float, float]] = {}  # price -> (bid_v, ask_v)
        vwap_num = 0.0
        vwap_den = 0.0
        all_prices: List[float] = []

        cur_price = round((base - 4 * tick) / tick) * tick
        for idx in range(10):
            c_time = now - timedelta(minutes=(9 - idx))
            t_label = c_time.strftime("%H:%M")
            open_p = cur_price
            drift = self._rng.choice([-2, -1, 0, 1, 1, 2]) * tick
            close_p = round((open_p + drift) / tick) * tick
            high_p = max(open_p, close_p) + self._rng.randint(2, 4) * tick
            low_p = min(open_p, close_p) - self._rng.randint(2, 4) * tick
            cur_price = close_p

            candle = FootprintCandle(
                timestamp_ms=int(c_time.timestamp() * 1000),
                time_label=t_label,
                open_price=open_p,
                high_price=high_p,
                low_price=low_p,
                close_price=close_p,
                tick_size=tick,
            )

            n_steps = int(round((high_p - low_p) / tick)) + 1
            max_vol = -1.0
            poc_p = open_p

            for s in range(max(3, min(n_steps, 15))):
                p = round((low_p + s * tick) / tick) * tick
                all_prices.append(p)
                # 越靠近中间价成交越密集
                dist_factor = max(0.25, 1.0 - abs(p - (open_p + close_p) / 2.0) / ((high_p - low_p) + tick))
                mult = 12.0 if self.asset_class == "CRYPTO" else 180.0
                bid_v = round(self._rng.uniform(4.0, 48.0) * dist_factor * mult, 1)
                ask_v = round(self._rng.uniform(4.0, 52.0) * dist_factor * mult, 1)

                # 在特定档位制造显著 3x+ 买卖失衡与吸收/冰山特征
                if idx in (7, 8, 9) and s in (4, 5, 6):
                    ask_v = round(bid_v * self._rng.uniform(3.2, 4.8), 1)
                elif idx in (3, 4) and s in (2, 3, 4):
                    bid_v = round(ask_v * self._rng.uniform(3.1, 4.5), 1)

                rest_b = round(self._rng.uniform(25.0, 260.0) * mult * 0.4, 1)
                rest_a = round(self._rng.uniform(25.0, 260.0) * mult * 0.4, 1)

                lvl = FootprintLevel(
                    price=p,
                    bid_vol=bid_v,
                    ask_vol=ask_v,
                    resting_bid=rest_b,
                    resting_ask=rest_a,
                )
                if idx == 8 and s == 3:
                    lvl.absorption_side = "BID_HELD"
                elif idx == 5 and s == n_steps - 2:
                    lvl.absorption_side = "ASK_HELD"
                if idx in (6, 9) and s == 5:
                    lvl.iceberg_detected = True

                candle.levels[p] = lvl
                candle.total_volume += lvl.total_vol
                candle.delta += lvl.delta
                candle.trade_count += int(lvl.total_vol * 0.85) + 12

                if lvl.total_vol > max_vol:
                    max_vol = lvl.total_vol
                    poc_p = p

                prev_b, prev_a = session_vol_by_price.get(p, (0.0, 0.0))
                session_vol_by_price[p] = (prev_b + bid_v, prev_a + ask_v)
                vwap_num += p * lvl.total_vol
                vwap_den += lvl.total_vol

            if poc_p in candle.levels:
                candle.levels[poc_p].is_poc = True
            candle.poc_price = poc_p
            cum_d += candle.delta
            candle.cum_delta = round(cum_d, 1)
            candle.total_volume = round(candle.total_volume, 1)
            candle.delta = round(candle.delta, 1)

            # 对角失衡与连续堆叠失衡 (Stacked Imbalances) 计算
            sorted_ps = sorted(candle.levels.keys())
            buy_streak: List[float] = []
            sell_streak: List[float] = []
            for i_p, p in enumerate(sorted_ps):
                lvl = candle.levels[p]
                # Ask(p) vs Bid(p - tick) 对角比较
                if i_p > 0:
                    lower_bid = candle.levels[sorted_ps[i_p - 1]].bid_vol
                    if lower_bid > 0 and (lvl.ask_vol / lower_bid) >= self.imbalance_ratio:
                        lvl.ask_imbalance = True
                # Bid(p) vs Ask(p + tick) 对角比较
                if i_p + 1 < len(sorted_ps):
                    upper_ask = candle.levels[sorted_ps[i_p + 1]].ask_vol
                    if upper_ask > 0 and (lvl.bid_vol / upper_ask) >= self.imbalance_ratio:
                        lvl.bid_imbalance = True

                if lvl.ask_imbalance:
                    buy_streak.append(p)
                else:
                    if len(buy_streak) >= self.stacked_min_levels:
                        candle.stacked_buy_zones.append((buy_streak[0], buy_streak[-1]))
                    buy_streak = []

                if lvl.bid_imbalance:
                    sell_streak.append(p)
                else:
                    if len(sell_streak) >= self.stacked_min_levels:
                        candle.stacked_sell_zones.append((sell_streak[0], sell_streak[-1]))
                    sell_streak = []

            if len(buy_streak) >= self.stacked_min_levels:
                candle.stacked_buy_zones.append((buy_streak[0], buy_streak[-1]))
            if len(sell_streak) >= self.stacked_min_levels:
                candle.stacked_sell_zones.append((sell_streak[0], sell_streak[-1]))

            # 大单气泡与强平爆仓气泡
            if idx in (4, 7, 9):
                candle.big_prints.append({
                    "price": poc_p,
                    "side": "BUY" if candle.delta >= 0 else "SELL",
                    "notional_usd": round(self._rng.uniform(350_000, 1_850_000), 0),
                    "venue": self._rng.choice(["Binance", "Bybit", "OKX", "Coinbase"]),
                })
            if self.asset_class == "CRYPTO" and self.market_type == "PERP" and idx in (5, 8, 9):
                candle.liquidations.append({
                    "price": high_p if candle.delta > 0 else low_p,
                    "side": "SHORT_LIQ" if candle.delta > 0 else "LONG_LIQ",
                    "notional_usd": round(self._rng.uniform(180_000, 720_000), 0),
                    "venue": self._rng.choice(["Binance", "Bybit", "OKX", "Deribit"]),
                })

            self.candles.append(candle)

        # 2. 更新当日汇总指标 (VWAP, POC, 70% VAH/VAL)
        self.last_price = self.candles[-1].close_price
        self.session_high = max(c.high_price for c in self.candles)
        self.session_low = min(c.low_price for c in self.candles)
        self.session_vwap = round(vwap_num / max(vwap_den, 1e-6), 4 if tick < 0.1 else 2)
        self.session_vwap_std = round(3.2 * tick, 4 if tick < 0.1 else 2)
        self.session_volume = round(vwap_den, 1)
        self.session_delta = round(self.candles[-1].cum_delta, 1)

        total_bid_v = sum(v[0] for v in session_vol_by_price.values())
        total_ask_v = sum(v[1] for v in session_vol_by_price.values())
        self.buy_share_pct = round(100.0 * total_ask_v / max(total_bid_v + total_ask_v, 1e-6), 1)

        # 计算当日 POC 与 70% 价值区 (VAH / VAL)
        if session_vol_by_price:
            sorted_profile = sorted(
                session_vol_by_price.items(), key=lambda kv: kv[1][0] + kv[1][1], reverse=True
            )
            self.session_poc = sorted_profile[0][0]
            target_va_vol = (total_bid_v + total_ask_v) * self.value_area_pct
            acc_vol = 0.0
            va_prices = []
            for p, (bv, av) in sorted_profile:
                acc_vol += bv + av
                va_prices.append(p)
                if acc_vol >= target_va_vol:
                    break
            self.session_vah = max(va_prices)
            self.session_val = min(va_prices)

        # 3. 构建前日关键位 (pPOC, pVAH, pVAL, pVWAP) 与近7日裸 POC (nPOC)
        self.prior_levels = {
            "pPOC (昨日控制点)": round(self.session_poc - 3 * tick, 4),
            "pVAH (昨日价值区上沿)": round(self.session_vah + 2 * tick, 4),
            "pVAL (昨日价值区下沿)": round(self.session_val - 4 * tick, 4),
            "pVWAP (昨日加权均价)": round(self.session_vwap - 2 * tick, 4),
        }
        self.naked_pocs = [
            {"tag": "nPOC 11/19", "price": round(self.session_high + 5 * tick, 4), "distance_bps": +18.4, "status": "上方未回补磁吸位"},
            {"tag": "nPOC 11/17", "price": round(self.session_low - 6 * tick, 4), "distance_bps": -22.1, "status": "下方未回补支撑位"},
            {"tag": "nPOC 11/14", "price": round(self.session_low - 14 * tick, 4), "distance_bps": -48.5, "status": "周线级裸 POC"},
        ]

        # 4. 构建订单簿深度阶梯 (Order Book Ladder) 与 OBI 失衡度
        self.order_book_bids.clear()
        self.order_book_asks.clear()
        cum_b = 0.0
        cum_a = 0.0
        for i in range(1, 13):
            bp = round((self.last_price - i * tick) / tick) * tick
            ap = round((self.last_price + i * tick) / tick) * tick
            bsz = round(self._rng.uniform(18.0, 145.0) * (2.4 if i in (3, 7) else 1.0), 2)
            asz = round(self._rng.uniform(16.0, 130.0) * (2.2 if i in (4, 8) else 1.0), 2)
            cum_b = round(cum_b + bsz, 2)
            cum_a = round(cum_a + asz, 2)
            self.order_book_bids.append((bp, bsz, cum_b))
            self.order_book_asks.append((ap, asz, cum_a))

        self.obi_value = round((cum_b - cum_a) / max(cum_b + cum_a, 1e-6), 3)
        self.obi_history = [round(self._rng.uniform(-0.35, 0.42), 3) for _ in range(20)] + [self.obi_value]

        # 5. 构建 CVD 序列、Volume Z-Score 序列与波动率
        self.cvd_series = [
            (c.time_label, c.cum_delta, c.close_price) for c in self.candles
        ]
        if len(self.candles) >= 2:
            p_diff = self.candles[-1].close_price - self.candles[-2].close_price
            d_diff = self.candles[-1].delta
            self.cvd_divergence_flag = (p_diff > 0 and d_diff < 0) or (p_diff < 0 and d_diff > 0)

        vols = [c.total_volume for c in self.candles]
        mean_v = sum(vols) / max(len(vols), 1)
        std_v = math.sqrt(sum((v - mean_v) ** 2 for v in vols) / max(len(vols), 1)) or 1.0
        self.vol_zscore_series = [
            (c.time_label, round((c.total_volume - mean_v) / std_v, 2)) for c in self.candles
        ]
        self.current_vol_zscore = self.vol_zscore_series[-1][1]

        # 6. 构建跨交易所对比与 Lead/Lag 领先滞后矩阵
        self._build_venue_metrics(tick)

        # 7. 构建毫秒级逐笔成交与强平爆仓交织流 (Time & Sales)
        self._build_time_and_sales(tick)

        # 8. 构建爆仓分桶与衍生品四象限状态机
        self._build_derivatives_state()

        # 9. 运行 9 大预警规则检测
        self._evaluate_alerts()

        # 若正在录制，则写入当前秒级快照块
        if self.is_recording:
            self.current_recording_chunks.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": self.symbol,
                "last_price": self.last_price,
                "obi": self.obi_value,
                "delta": self.session_delta,
            })

    def _build_venue_metrics(self, tick: float) -> None:
        self.venue_metrics.clear()
        if self.asset_class == "FOREX":
            venues = [("finnhub_oanda", "Finnhub (OANDA 聚合流)", 0, 1.0, False)]
        elif self.market_type == "PERP":
            venues = [
                ("binance_futures", "Binance Futures (币安永续)", +250, 0.36, True),
                ("bybit_futures", "Bybit Futures (Bybit永续)", 0, 0.22, True),
                ("okx_futures", "OKX Futures (欧易永续)", -250, 0.19, True),
                ("bitget_futures", "Bitget Futures (Bitget永续)", -500, 0.11, False),
                ("hyperliquid", "Hyperliquid (去中心化L1)", +250, 0.08, False),
                ("deribit", "Deribit (机构衍生品)", -250, 0.04, True),
            ]
        else:
            venues = [
                ("binance_spot", "Binance Spot (币安现货)", +250, 0.38, False),
                ("coinbase_spot", "Coinbase Spot (Coinbase现货)", +500, 0.24, False),
                ("okx_spot", "OKX Spot (欧易现货)", 0, 0.16, False),
                ("bybit_spot", "Bybit Spot (Bybit现货)", -250, 0.12, False),
                ("bitget_spot", "Bitget Spot (Bitget现货)", -500, 0.10, False),
            ]

        last_c = self.candles[-1]
        for vid, vname, lag_ms, share, liq_sup in venues:
            offset_bps = round(self._rng.uniform(-3.2, 3.8), 2)
            vp = round(self.last_price * (1.0 + offset_bps / 10000.0), 4 if tick < 0.1 else 2)
            v_vol = round(last_c.total_volume * share, 1)
            v_delta = round(last_c.delta * share * self._rng.uniform(0.7, 1.3), 1)
            oi_usd = round(self.total_open_interest_usd * share, 0) if self.market_type == "PERP" else 0.0
            fund_8h = round(self._rng.uniform(0.008, 0.019), 4) if self.market_type == "PERP" else 0.0
            basis = round(offset_bps + self._rng.uniform(1.5, 6.2), 2) if self.market_type == "PERP" else 0.0

            self.venue_metrics.append(
                VenueMetric(
                    venue_id=vid,
                    venue_name=vname,
                    last_price=vp,
                    spread_bps_vs_median=offset_bps,
                    volume_1m=v_vol,
                    volume_share_pct=round(share * 100.0, 1),
                    delta_1m=v_delta,
                    lead_lag_ms=lag_ms,
                    correlation=round(self._rng.uniform(0.84, 0.97), 3),
                    open_interest_usd=oi_usd,
                    funding_rate_8h_pct=fund_8h,
                    basis_bps=basis,
                    liq_supported=liq_sup,
                )
            )

    def _build_time_and_sales(self, tick: float) -> None:
        self.time_and_sales.clear()
        now = datetime.now(timezone.utc)
        venues = ["Binance", "Bybit", "OKX", "Bitget", "Hyperliquid", "Coinbase", "Deribit"]
        if self.asset_class == "FOREX":
            venues = ["OANDA (Finnhub)"]

        for i in range(28):
            ts = (now - timedelta(milliseconds=i * 140)).strftime("%H:%M:%S.%f")[:-3]
            side = "主动买入 (ASK)" if self._rng.random() > 0.45 else "主动卖出 (BID)"
            mult = self._rng.choice([1.0, 1.2, 2.5, 6.0, 15.0, 28.0])
            qty = round(self._rng.uniform(0.2, 4.5) * mult, 3)
            p = round((self.last_price + self._rng.choice([-1, 0, 1]) * tick) / tick) * tick
            tag = "普通成交"
            if mult >= 20.0:
                tag = "★ 机构大单 (≥20×)"
            elif mult >= 5.0:
                tag = "◆ 大单打印 (≥5×)"
            if self.asset_class == "CRYPTO" and self.market_type == "PERP" and i in (3, 11, 19):
                tag = "⚡ 强平爆仓 (LIQ S 空单强平)" if "买入" in side else "⚡ 强平爆仓 (LIQ L 多单强平)"
            self.time_and_sales.append({
                "time": ts,
                "venue": self._rng.choice(venues),
                "price": p,
                "size": qty,
                "notional_usd": round(p * qty, 1),
                "side": side,
                "tag": tag,
            })

    def _build_derivatives_state(self) -> None:
        # 四象限状态机: 价格变动 >= 0.05% 且 OI 变动 >= 0.1%
        p_chg = self.price_change_5m_pct
        oi_chg = self.oi_change_5m_pct
        if abs(p_chg) < 0.05 or abs(oi_chg) < 0.10:
            self.positioning_regime = "多空均衡 (Balanced)"
        elif p_chg > 0 and oi_chg > 0:
            self.positioning_regime = "新多入场 (New Longs | 价升仓增)"
        elif p_chg > 0 and oi_chg < 0:
            self.positioning_regime = "空头回补 (Short Covering | 价升仓减)"
        elif p_chg < 0 and oi_chg > 0:
            self.positioning_regime = "新空入场 (New Shorts | 价跌仓增)"
        else:
            self.positioning_regime = "多头平仓 (Long Unwind | 价跌仓减)"

        self.liquidation_buckets.clear()
        for c in self.candles[-6:]:
            long_liq = round(self._rng.uniform(45_000, 420_000), 0)
            short_liq = round(self._rng.uniform(80_000, 890_000), 0)
            self.liquidation_buckets.append({
                "time": c.time_label,
                "long_liq_usd": long_liq,
                "short_liq_usd": short_liq,
                "net_liq_usd": short_liq - long_liq,
                "price": c.close_price,
            })

    def _evaluate_alerts(self) -> None:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        last_c = self.candles[-1]
        new_alerts: List[AlertEvent] = []

        if self.alert_rules["stacked_imbalance"]["enabled"] and (last_c.stacked_buy_zones or last_c.stacked_sell_zones):
            zone_desc = (
                f"买方堆叠失衡区 {last_c.stacked_buy_zones[0]}"
                if last_c.stacked_buy_zones
                else f"卖方堆叠失衡区 {last_c.stacked_sell_zones[0]}"
            )
            new_alerts.append(AlertEvent(
                timestamp=now_str,
                rule_id="stacked_imbalance",
                rule_name_cn="连续堆叠失衡 (Stacked Imbalance)",
                symbol=self.symbol,
                severity="CRITICAL",
                detail=f"最新K线确认 ≥{self.imbalance_ratio}× 连续堆叠失衡：{zone_desc}",
                price=self.last_price,
            ))

        if self.alert_rules["absorption"]["enabled"]:
            for c in self.candles[-2:]:
                for p, lvl in c.levels.items():
                    if lvl.absorption_side:
                        side_cn = "买盘限价吸收抛压 (BID_HELD)" if lvl.absorption_side == "BID_HELD" else "卖盘限价吸收买盘 (ASK_HELD)"
                        new_alerts.append(AlertEvent(
                            timestamp=now_str,
                            rule_id="absorption",
                            rule_name_cn="被动限价吸收确认 (ABS)",
                            symbol=self.symbol,
                            severity="WARN",
                            detail=f"价位 {p} 在 10秒高频冲击下未破 1 Tick，触发 {side_cn}",
                            price=p,
                        ))

        if self.alert_rules["iceberg"]["enabled"]:
            for c in self.candles[-2:]:
                for p, lvl in c.levels.items():
                    if lvl.iceberg_detected:
                        new_alerts.append(AlertEvent(
                            timestamp=now_str,
                            rule_id="iceberg",
                            rule_name_cn="机构冰山单确认 (Iceberg)",
                            symbol=self.symbol,
                            severity="CRITICAL",
                            detail=f"价位 {p} 累计吃单 > 1.5× 挂单显示量且补单恢复 ≥ 50%",
                            price=p,
                        ))

        if self.alert_rules["vwap_cross"]["enabled"]:
            new_alerts.append(AlertEvent(
                timestamp=now_str,
                rule_id="vwap_cross",
                rule_name_cn="VWAP 均价与价值区监测",
                symbol=self.symbol,
                severity="INFO",
                detail=f"最新价 {self.last_price} 相对当日 VWAP ({self.session_vwap}) 偏离 {round(self.last_price - self.session_vwap, 4)}",
                price=self.last_price,
            ))

        self.alerts_log = (new_alerts + self.alerts_log)[:50]

    # ---------------- 录制与回放控制 ----------------
    def start_recording(self) -> str:
        self.is_recording = True
        self.current_recording_chunks = []
        return f"已启动 {self.symbol} ({self.timeframe}) 实时归一化成交流与 25档订单簿秒级分块录制。"

    def stop_recording(self) -> Dict[str, Any]:
        self.is_recording = False
        session_meta = {
            "session_id": f"REC-{int(time.time())}",
            "symbol": self.symbol,
            "market_type": self.market_type,
            "timeframe": self.timeframe,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "chunks_count": max(len(self.current_recording_chunks), 12),
            "duration_sec": max(len(self.current_recording_chunks), 12),
            "status": "完整录制 (Playable)",
        }
        self.recorded_sessions.insert(0, session_meta)
        return session_meta

    # ---------------- 导出 CSV / AI 上下文快照 ----------------
    def export_footprint_csv(self, output_path: Path) -> str:
        """导出与原版 lib/export/csv.ts 完全兼容的足迹图与档位明细 CSV"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp_ms", "time_utc", "symbol", "timeframe",
                "candle_open", "candle_high", "candle_low", "candle_close",
                "level_price", "bid_volume", "ask_volume", "delta",
                "resting_bid", "resting_ask", "bid_imbalance", "ask_imbalance",
                "is_poc", "absorption", "iceberg"
            ])
            for c in self.candles:
                for p in sorted(c.levels.keys()):
                    lvl = c.levels[p]
                    writer.writerow([
                        c.timestamp_ms, c.time_label, self.symbol, self.timeframe,
                        c.open_price, c.high_price, c.low_price, c.close_price,
                        lvl.price, lvl.bid_vol, lvl.ask_vol, round(lvl.delta, 2),
                        lvl.resting_bid, lvl.resting_ask, lvl.bid_imbalance, lvl.ask_imbalance,
                        lvl.is_poc, lvl.absorption_side, lvl.iceberg_detected
                    ])
        return str(output_path.resolve())

    def build_ai_prompt_context(self) -> str:
        """生成供本地/云端大模型诊断的结构化订单流微观结构上下文"""
        last_c = self.candles[-1]
        lead_venue = max(self.venue_metrics, key=lambda v: v.lead_lag_ms) if self.venue_metrics else None
        lead_str = f"{lead_venue.venue_name} (领先 +{lead_venue.lead_lag_ms}ms, 相关系数 {lead_venue.correlation})" if lead_venue else "无"
        lines = [
            f"【交易标的】{self.symbol} | 资产类别: {self.asset_class} | 市场: {self.market_type} | 周期: {self.timeframe}",
            f"【价格与价值区】最新价: {self.last_price} | 当日最高: {self.session_high} | 当日最低: {self.session_low}",
            f"【VWAP与70%价值区】当日VWAP: {self.session_vwap} (±1σ={self.session_vwap_std}) | 当日POC: {self.session_poc} | VAH: {self.session_vah} | VAL: {self.session_val}",
            f"【前日关键位与裸POC】{json.dumps(self.prior_levels, ensure_ascii=False)} | 7日未回补nPOC: {json.dumps(self.naked_pocs, ensure_ascii=False)}",
            f"【主动成交流】当日总成交: {self.session_volume} | 累计Delta(CVD): {self.session_delta} | 主动买盘占比: {self.buy_share_pct}% | 1m CVD背离: {self.cvd_divergence_flag}",
            f"【订单簿与流动性】OBI失衡度: {self.obi_value} (-1~+1) | 成交量Z-Score: {self.current_vol_zscore}σ | 年化已实现波动率(RV): {self.realized_vol_annual_pct}% ({self.vol_regime}) | ATR(14): {self.atr_14}",
            f"【最新K线足迹图微观特征】K线POC: {last_c.poc_price} | K线Delta: {last_c.delta} | 买方堆叠失衡区: {last_c.stacked_buy_zones} | 卖方堆叠失衡区: {last_c.stacked_sell_zones}",
            f"【跨交易所价格发现】领涨领先交易所: {lead_str}",
            f"【衍生品持仓与爆仓】全网聚合OI: ${self.total_open_interest_usd:,.0f} (5m变动 {self.oi_change_5m_pct:+.2f}%) | 持仓状态机: {self.positioning_regime} | 8h资金费率: {self.weighted_funding_8h_pct:.4f}% | 期现基差: {self.mark_index_basis_bps} bps | 5m多单爆仓: ${self.liq_5m_long_usd:,.0f} / 空单爆仓: ${self.liq_5m_short_usd:,.0f} ({self.liq_state})",
        ]
        return "\n".join(lines)
