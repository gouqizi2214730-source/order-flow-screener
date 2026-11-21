#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order Flow Screener (订单流微观结构量化终端) 纯原生 PySide6 (Qt 6) 全中文现代深色桌面客户端 (gui_app.py)
严格遵循用户记忆与打包规范：
1. 纯原生 PySide6 (Qt 6) 实现，启用 Per-Monitor v2 HiDPI 感知与 PassThrough 缩放策略，彻底杜绝字体与图标发虚。
2. 严禁依赖浏览器或 Web 套壳（无 Streamlit、无 Tkinter），所有子进程与网络任务均采用后台线程 + `CREATE_NO_WINDOW`。
3. 运行时绑定 `AppUserModelID` 与 Win32 `WM_SETICON` 256px 多尺寸高清图标 (`app_icon_v230.ico`)，并提供 Windows 系统托盘 (`QSystemTrayIcon`) 后台常驻。
4. 100% 完整覆盖源项目 zadescoxp/order-flow-screener (v2.3.0) 的全部功能面板与新增 AI/数据源/自动更新中心：
   - 面板1：足迹图与流动性热力图终端 (Footprint Chart: Bid×Ask / Delta / Volume 三模式、≥3× 失衡与堆叠失衡、
     当日 POC/VAH/VAL 70% 价值区、VWAP ±1σ/±2σ、大单与爆仓气泡、挂单深度热力图 & 成交热力图、ABS 吸收与 Iceberg 冰山单、十字准星联动)
   - 面板2：订单簿深度、OBI 失衡度、累计深度曲线与毫秒级逐笔成交 (Order Book Ladder, OBI Gauge, Market Depth ±10/25bp, Time & Sales Tape)
   - 面板3：跨交易所对比、领涨/滞后相关性与前日关键位 (Venues Lead/Lag ±2s 250ms 步进相关性, Prior-Session pPOC/pVAH/pVAL/pVWAP & 7日裸 nPOC)
   - 面板4：衍生品合约监控与量化副图 (Open Interest 四象限状态机、8h 资金费率、期现基差、强平爆仓级联 Cascade、CVD 背离、Volume Z-Score、已实现波动率 RV/ATR/Parkinson)
   - 面板5：9大智能预警引擎、实时录制与 1×/5×/20× 虚拟时钟回放及 CSV/PNG/Markdown/HTML 导出
   - 面板6：AI 订单流微观结构流式解读与本地/云端大模型配置中心 (Ollama, LM Studio, vLLM 免Key即连 + DeepSeek/千问/硅基流动/GLM/Kimi/OpenAI/Gemini/Claude + 本地 127.0.0.1:8787 OpenAI 兼容服务)
   - 面板7：数据源接口管理中心 (12大加密货币永续/现货与 Finnhub OANDA 外汇接口配置、.env.local 同步、连通性并发探测)
   - 面板8：应用内自动更新与上游同步中心 (检查 gouqizi2214730-source 与上游 zadescoxp 最新版本、一键 `/VERYSILENT` 静默覆盖安装)
"""

import ctypes
import json
import math
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import (
    Qt,
    QTimer,
    QRectF,
    QPointF,
    QThread,
    Signal,
    QSize,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient,
    QAction,
    QPixmap,
    QCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QFrame,
    QSplitter,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
)

from order_flow_engine import OrderFlowEngine, FootprintCandle, FootprintLevel
from data_sources import DataSourceManager, CRYPTO_INSTRUMENTS, FOREX_INSTRUMENTS
from llm_providers import LLMProviderManager
from updater import AutoUpdater, APP_VERSION


# ---------------- Windows HiDPI 与任务栏高清图标强制绑定 ----------------
def setup_windows_hidpi_and_appid() -> None:
    if sys.platform == "win32":
        try:
            # Per-Monitor v2 DPI Awareness (-4)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass
        try:
            appid = "gouqizi2214730.OrderFlowScreener.CN.v230"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass


def bind_win32_window_icon(hwnd: int, ico_path: str) -> None:
    """使用 Win32 LoadImageW + WM_SETICON 强制将 256px/32px/16px 图标绑定至窗口句柄"""
    if sys.platform != "win32" or not os.path.exists(ico_path):
        return
    try:
        user32 = ctypes.windll.user32
        LR_LOADFROMFILE = 0x00000010
        IMAGE_ICON = 1
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
        hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if hicon_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception:
        pass


# ---------------- 现代深色卡片主题样式表 (Microsoft YaHei) ----------------
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0B101E;
    color: #E2E8F0;
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
}
QFrame#TopControlCard, QFrame#KpiStripCard, QFrame#SectionCard {
    background-color: #131B2E;
    border: 1px solid #1E293B;
    border-radius: 8px;
}
QLabel#HeroPrice {
    color: #10B981;
    font-size: 20px;
    font-weight: bold;
}
QLabel#KpiTitle {
    color: #94A3B8;
    font-size: 11px;
}
QLabel#KpiValue {
    color: #F8FAFC;
    font-size: 13px;
    font-weight: bold;
}
QLabel#SectionHeader {
    color: #38BDF8;
    font-size: 14px;
    font-weight: bold;
}
QPushButton {
    background-color: #1E293B;
    color: #F1F5F9;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #38BDF8;
}
QPushButton#PrimaryBtn {
    background-color: #0284C7;
    color: #FFFFFF;
    border: 1px solid #38BDF8;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0369A1;
}
QPushButton#SuccessBtn {
    background-color: #059669;
    color: #FFFFFF;
    border: 1px solid #10B981;
}
QPushButton#DangerBtn {
    background-color: #E11D48;
    color: #FFFFFF;
    border: 1px solid #F43F5E;
}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0F172A;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 8px;
}
QComboBox:hover, QLineEdit:focus {
    border-color: #38BDF8;
}
QTabWidget::pane {
    border: 1px solid #1E293B;
    background-color: #0F172A;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #131B2E;
    color: #94A3B8;
    border: 1px solid #1E293B;
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #0284C7;
    color: #FFFFFF;
    border-color: #38BDF8;
}
QTableWidget {
    background-color: #0F172A;
    alternate-background-color: #131B2E;
    color: #E2E8F0;
    gridline-color: #1E293B;
    border: 1px solid #1E293B;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #1E293B;
    color: #38BDF8;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #0F172A;
}
QTextEdit {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 8px;
}
QProgressBar {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 5px;
    text-align: center;
    color: #FFFFFF;
}
QProgressBar::chunk {
    background-color: #10B981;
    border-radius: 4px;
}
"""


# ---------------- 后台工作线程：AI 流式推理与数据源并发探测 ----------------
class LLMStreamWorker(QThread):
    token_received = Signal(str)
    finished_full = Signal(str)

    def __init__(self, llm_mgr: LLMProviderManager, prompt: str):
        super().__init__()
        self.llm_mgr = llm_mgr
        self.prompt = prompt

    def run(self) -> None:
        full_text = self.llm_mgr.chat_completion(
            self.prompt,
            stream_callback=lambda chunk: self.token_received.emit(chunk),
        )
        self.finished_full.emit(full_text)


class DataSourceProbeWorker(QThread):
    progress_updated = Signal(int, str, dict)
    all_completed = Signal(list)

    def __init__(self, ds_mgr: DataSourceManager):
        super().__init__()
        self.ds_mgr = ds_mgr

    def run(self) -> None:
        sids = list(self.ds_mgr.sources.keys())
        total = len(sids)
        results = []
        for idx, sid in enumerate(sids, 1):
            res = self.ds_mgr.test_connectivity(sid)
            results.append(res)
            pct = int(idx * 100 / max(total, 1))
            self.progress_updated.emit(pct, sid, res)
        self.all_completed.emit(results)


# ---------------- 自定义 DPR 高清自绘足迹图与热力图画布 (FootprintCanvasWidget) ----------------
class FootprintCanvasWidget(QWidget):
    """
    原生 QPainter 高帧率自绘足迹图 + 挂单流动性热力图 + 当日成交量分布 Profile + VWAP ±1σ/±2σ +
    POC/VAH/VAL 关键线 + 昨日 pPOC/裸 nPOC + 大单气泡/强平气泡 + ABS 吸收与冰山单菱形标记 + 十字准星联动
    """

    def __init__(self, engine: OrderFlowEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(460)
        self.setMouseTracking(True)
        self.hover_pos: Optional[QPointF] = None

    def mouseMoveEvent(self, event) -> None:
        self.hover_pos = event.position()
        self.update()

    def leaveEvent(self, event) -> None:
        self.hover_pos = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#0B101E"))

        candles = self.engine.candles
        if not candles:
            return

        # 收集所有价格档位
        all_prices = sorted({p for c in candles for p in c.levels.keys()}, reverse=True)
        if not all_prices:
            return

        top_pad = 34
        bottom_pad = 72
        left_profile_w = 115
        right_axis_w = 92
        chart_x0 = left_profile_w + 8
        chart_w = max(200, w - chart_x0 - right_axis_w - 8)
        chart_h = max(160, h - top_pad - bottom_pad)

        n_rows = len(all_prices)
        row_h = max(18.0, min(32.0, chart_h / max(n_rows, 1)))
        n_cols = len(candles)
        col_w = chart_w / max(n_cols, 1)

        price_to_y: Dict[float, float] = {}
        for r_idx, p in enumerate(all_prices):
            price_to_y[p] = top_pad + r_idx * row_h

        # 1. 绘制顶部标题与图例条
        painter.setPen(QColor("#38BDF8"))
        painter.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        mode_cn = {"BID_ASK": "买×卖双列 (Bid × Ask)", "DELTA": "净差值 (Delta)", "VOLUME": "总成交量 (Volume)"}.get(
            self.engine.cell_mode, "Bid × Ask"
        )
        header_text = (
            f"足迹图与流动性热力终端 [{self.engine.symbol} · {self.engine.timeframe}]  |  "
            f"模式: {mode_cn}  |  失衡高亮 ≥{self.engine.imbalance_ratio}×  |  "
            f"POC: {self.engine.session_poc}  |  VAH: {self.engine.session_vah}  |  VAL: {self.engine.session_val}  |  VWAP: {self.engine.session_vwap}"
        )
        painter.drawText(12, 22, header_text)

        # 2. 绘制左侧当日成交量分布 (Session Volume Profile + 70% Value Area 阴影)
        session_bid_by_p: Dict[float, float] = {}
        session_ask_by_p: Dict[float, float] = {}
        max_prof_vol = 1.0
        for c in candles:
            for p, lvl in c.levels.items():
                session_bid_by_p[p] = session_bid_by_p.get(p, 0.0) + lvl.bid_vol
                session_ask_by_p[p] = session_ask_by_p.get(p, 0.0) + lvl.ask_vol
                max_prof_vol = max(max_prof_vol, session_bid_by_p[p] + session_ask_by_p[p])

        for p in all_prices:
            y = price_to_y[p]
            bv = session_bid_by_p.get(p, 0.0)
            av = session_ask_by_p.get(p, 0.0)
            tot_v = bv + av
            in_va = self.engine.session_val <= p <= self.engine.session_vah
            bar_max_w = left_profile_w - 14
            b_w = (bv / max_prof_vol) * bar_max_w
            a_w = (av / max_prof_vol) * bar_max_w

            # 背景带
            bg_col = QColor(30, 58, 138, 70) if in_va else QColor(15, 23, 42, 90)
            painter.fillRect(QRectF(6, y + 1, bar_max_w, row_h - 2), bg_col)
            # 卖方主动量 (红) + 买方主动量 (绿)
            painter.fillRect(QRectF(6, y + 3, b_w, row_h - 6), QColor(244, 63, 94, 190 if in_va else 120))
            painter.fillRect(QRectF(6 + b_w, y + 3, a_w, row_h - 6), QColor(16, 185, 129, 190 if in_va else 120))

            if abs(p - self.engine.session_poc) < 1e-6:
                painter.setPen(QPen(QColor("#FACC15"), 2))
                painter.drawRect(QRectF(5, y + 1, bar_max_w + 2, row_h - 2))

        # 3. 计算挂单深度热力图 98 分位上限
        max_resting = 1.0
        for c in candles:
            for lvl in c.levels.values():
                max_resting = max(max_resting, lvl.resting_bid + lvl.resting_ask)

        # 4. 逐根绘制足迹图 K 线、挂单深度热力背景、Bid×Ask 单元格、失衡高亮、POC 金框、气泡与吸收/冰山标记
        font_cell = QFont("Consolas", 8, QFont.Bold)
        painter.setFont(font_cell)

        vwap_pts: List[QPointF] = []

        for c_idx, c in enumerate(candles):
            cx = chart_x0 + c_idx * col_w
            cell_x = cx + 8
            cell_w = max(36.0, col_w - 14)

            # OHLC 侧边色条
            is_bull = c.close_price >= c.open_price
            ohlc_color = QColor("#10B981") if is_bull else QColor("#F43F5E")
            y_high = price_to_y.get(c.high_price, top_pad)
            y_low = price_to_y.get(c.low_price, top_pad + chart_h) + row_h
            painter.fillRect(QRectF(cx + 2, y_high + 2, 4, max(6.0, y_low - y_high - 4)), ohlc_color)

            for p, lvl in c.levels.items():
                if p not in price_to_y:
                    continue
                y = price_to_y[p]
                rect = QRectF(cell_x, y + 1, cell_w, row_h - 2)

                # (a) 挂单流动性热力图底色 (深蓝 -> 青 -> 黄)
                if self.engine.show_resting_heatmap:
                    intensity = min(1.0, (lvl.resting_bid + lvl.resting_ask) / max_resting)
                    if intensity < 0.5:
                        r_c, g_c, b_c = 15, int(40 + intensity * 220), int(90 + intensity * 260)
                    else:
                        t_i = (intensity - 0.5) * 2.0
                        r_c, g_c, b_c = int(20 + t_i * 230), int(150 + t_i * 95), int(220 - t_i * 160)
                    painter.fillRect(rect, QColor(r_c, g_c, b_c, 75))

                # (b) 成交量/Delta 强度前景填充
                if self.engine.show_traded_heatmap:
                    d_col = QColor(16, 185, 129, 65) if lvl.delta >= 0 else QColor(244, 63, 94, 65)
                    painter.fillRect(rect, d_col)

                # (c) 单K线 POC 亮金色外框
                if lvl.is_poc:
                    painter.setPen(QPen(QColor("#FACC15"), 1.8))
                    painter.drawRect(rect)
                else:
                    painter.setPen(QPen(QColor("#1E293B"), 0.8))
                    painter.drawRect(rect)

                # (d) 单元格文字 (Bid x Ask / Delta / Volume) + 失衡高亮着色
                if self.engine.cell_mode == "BID_ASK":
                    half_w = cell_w / 2.0
                    bid_rect = QRectF(cell_x + 2, y + 1, half_w - 3, row_h - 2)
                    ask_rect = QRectF(cell_x + half_w + 1, y + 1, half_w - 3, row_h - 2)
                    if lvl.bid_imbalance:
                        painter.fillRect(bid_rect, QColor(244, 63, 94, 140))
                    if lvl.ask_imbalance:
                        painter.fillRect(ask_rect, QColor(16, 185, 129, 140))

                    painter.setPen(QColor("#FCA5A5") if lvl.bid_imbalance else QColor("#CBD5E1"))
                    painter.drawText(bid_rect, Qt.AlignRight | Qt.AlignVCenter, f"{lvl.bid_vol:.0f}")
                    painter.setPen(QColor("#6EE7B7") if lvl.ask_imbalance else QColor("#CBD5E1"))
                    painter.drawText(ask_rect, Qt.AlignLeft | Qt.AlignVCenter, f"{lvl.ask_vol:.0f}")
                elif self.engine.cell_mode == "DELTA":
                    painter.setPen(QColor("#34D399") if lvl.delta >= 0 else QColor("#FB7185"))
                    painter.drawText(rect, Qt.AlignCenter, f"{lvl.delta:+.0f}")
                else:
                    painter.setPen(QColor("#F8FAFC"))
                    painter.drawText(rect, Qt.AlignCenter, f"{lvl.total_vol:.0f}")

                # (e) 微观结构标记：被动限价吸收 (ABS) 与机构冰山单 (Iceberg 冰蓝菱形)
                if self.engine.show_microstructure:
                    if lvl.absorption_side:
                        abs_col = QColor("#10B981") if lvl.absorption_side == "BID_HELD" else QColor("#F43F5E")
                        painter.setPen(QPen(abs_col, 2))
                        painter.drawRect(rect.adjusted(1, 1, -1, -1))
                        painter.setPen(abs_col)
                        painter.drawText(rect.adjusted(2, 0, 0, 0), Qt.AlignLeft | Qt.AlignTop, "ABS")
                    if lvl.iceberg_detected:
                        painter.setBrush(QBrush(QColor("#38BDF8")))
                        painter.setPen(QPen(QColor("#FFFFFF"), 1))
                        cx_ice = cell_x + cell_w - 7
                        cy_ice = y + row_h / 2.0
                        painter.drawEllipse(QPointF(cx_ice, cy_ice), 4.5, 4.5)

            # (f) 大单气泡与强平爆仓圆环气泡
            for bp in c.big_prints:
                bp_y = price_to_y.get(bp["price"], top_pad + chart_h / 2) + row_h / 2
                bp_x = cx + col_w / 2
                col_b = QColor(16, 185, 129, 165) if bp["side"] == "BUY" else QColor(244, 63, 94, 165)
                painter.setBrush(QBrush(col_b))
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                painter.drawEllipse(QPointF(bp_x, bp_y), 11, 11)

            for lq in c.liquidations:
                lq_y = price_to_y.get(lq["price"], top_pad + 15) + row_h / 2
                lq_x = cx + col_w - 12
                col_l = QColor(16, 185, 129, 210) if lq["side"] == "SHORT_LIQ" else QColor(244, 63, 94, 210)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(col_l, 2.5))
                painter.drawEllipse(QPointF(lq_x, lq_y), 9, 9)

            # 收集 VWAP 轨迹点
            closest_p = min(all_prices, key=lambda pr: abs(pr - self.engine.session_vwap))
            vwap_pts.append(QPointF(cx + col_w / 2.0, price_to_y[closest_p] + row_h / 2.0))

        # 5. 绘制当日 VWAP 连线与 Session POC / VAH / VAL 水平参考线
        if len(vwap_pts) >= 2:
            painter.setPen(QPen(QColor("#38BDF8"), 2.2))
            for i in range(len(vwap_pts) - 1):
                painter.drawLine(vwap_pts[i], vwap_pts[i + 1])

        def draw_horiz_level(price_val: float, label: str, color_hex: str, pen_style=Qt.DashLine) -> None:
            closest = min(all_prices, key=lambda pr: abs(pr - price_val))
            ly = price_to_y[closest] + row_h / 2.0
            pen = QPen(QColor(color_hex), 1.4, pen_style)
            painter.setPen(pen)
            painter.drawLine(int(chart_x0), int(ly), int(chart_x0 + chart_w), int(ly))
            painter.drawText(int(chart_x0 + chart_w + 4), int(ly + 4), f"{label} {price_val}")

        draw_horiz_level(self.engine.session_poc, "POC", "#FACC15", Qt.SolidLine)
        draw_horiz_level(self.engine.session_vah, "VAH", "#A855F7", Qt.DashLine)
        draw_horiz_level(self.engine.session_val, "VAL", "#A855F7", Qt.DashLine)

        # 6. 绘制右侧价格坐标轴
        painter.setFont(QFont("Consolas", 8))
        for p in all_prices:
            y = price_to_y[p]
            is_last = abs(p - self.engine.last_price) < 1e-6
            if is_last:
                painter.fillRect(QRectF(chart_x0 + chart_w + 2, y + 1, right_axis_w - 6, row_h - 2), QColor("#0284C7"))
                painter.setPen(QColor("#FFFFFF"))
            else:
                painter.setPen(QColor("#94A3B8"))
            painter.drawText(
                QRectF(chart_x0 + chart_w + 6, y, right_axis_w - 10, row_h),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{p}",
            )

        # 7. 绘制底部 Summary 汇总统计条 (Volume / Delta / Cum Delta / Trades)
        sum_y0 = top_pad + n_rows * row_h + 6
        if sum_y0 + 52 > h:
            sum_y0 = h - 56
        painter.fillRect(QRectF(0, sum_y0, w, 54), QColor("#0F172A"))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
        row_labels = [("成交量 Vol", "total_volume"), ("净差 Delta", "delta"), ("累计 CVD", "cum_delta")]
        for r_i, (r_title, attr) in enumerate(row_labels):
            ry = sum_y0 + 4 + r_i * 16
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(10, int(ry + 12), r_title)
            for c_idx, c in enumerate(candles):
                cx = chart_x0 + c_idx * col_w
                val = getattr(c, attr)
                if attr in ("delta", "cum_delta"):
                    painter.setPen(QColor("#34D399") if val >= 0 else QColor("#FB7185"))
                    txt = f"{val:+.0f}"
                else:
                    painter.setPen(QColor("#E2E8F0"))
                    txt = f"{val:.0f}"
                painter.drawText(QRectF(cx, ry, col_w, 16), Qt.AlignCenter, txt)

        # 8. 十字准星联动与悬停挂单深度浮窗
        if self.hover_pos:
            hx = self.hover_pos.x()
            hy = self.hover_pos.y()
            if chart_x0 <= hx <= chart_x0 + chart_w and top_pad <= hy <= top_pad + n_rows * row_h:
                painter.setPen(QPen(QColor(148, 163, 184, 140), 1, Qt.DotLine))
                painter.drawLine(int(hx), top_pad, int(hx), int(top_pad + n_rows * row_h))
                painter.drawLine(int(chart_x0), int(hy), int(chart_x0 + chart_w), int(hy))

                c_idx = min(n_cols - 1, max(0, int((hx - chart_x0) / col_w)))
                r_idx = min(n_rows - 1, max(0, int((hy - top_pad) / row_h)))
                hov_c = candles[c_idx]
                hov_p = all_prices[r_idx]
                hov_lvl = hov_c.levels.get(hov_p)
                if hov_lvl:
                    tip = (
                        f"时间 {hov_c.time_label} | 价位 {hov_p} | "
                        f"主动卖(Bid): {hov_lvl.bid_vol:.1f} × 主动买(Ask): {hov_lvl.ask_vol:.1f} | "
                        f"Delta: {hov_lvl.delta:+.1f} | 挂单深度(Resting): {hov_lvl.resting_bid + hov_lvl.resting_ask:.1f}"
                    )
                    tip_rect = QRectF(chart_x0 + 8, top_pad + 4, min(chart_w - 16, 620), 24)
                    painter.fillRect(tip_rect, QColor(15, 23, 42, 230))
                    painter.setPen(QColor("#38BDF8"))
                    painter.drawRect(tip_rect)
                    painter.setPen(QColor("#F8FAFC"))
                    painter.drawText(tip_rect.adjusted(8, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, tip)


# ---------------- 双轴对比与量化副图自绘画布 (CVD + Volume Z-Score + 强平爆仓柱) ----------------
class DualAxisStudyCanvas(QWidget):
    """原生自绘双轴对比副图：累计成交量差 CVD vs 价格双轴叠加 + Volume Z-Score 异常柱 + 十字准星"""

    def __init__(self, engine: OrderFlowEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(210)
        self.setMouseTracking(True)
        self.hover_x: Optional[float] = None

    def mouseMoveEvent(self, event) -> None:
        self.hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:
        self.hover_x = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#0B101E"))

        series = self.engine.cvd_series
        z_series = self.engine.vol_zscore_series
        if len(series) < 2:
            return

        pad_l, pad_r, pad_t, pad_b = 58, 68, 28, 28
        cw = max(120, w - pad_l - pad_r)
        ch = max(80, h - pad_t - pad_b)

        painter.setPen(QColor("#38BDF8"))
        painter.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        div_txt = " [⚠️ 检测到 1分钟 CVD 与价格斜率背离]" if self.engine.cvd_divergence_flag else " [CVD 与价格趋势同步]"
        painter.drawText(
            12,
            19,
            f"双轴量化副图：累计成交量差 (CVD 左轴-青色) vs 价格走势 (右轴-金色) & 成交量 Z-Score 柱{div_txt}",
        )

        cvds = [pt[1] for pt in series]
        prices = [pt[2] for pt in series]
        min_c, max_c = min(cvds), max(cvds)
        if abs(max_c - min_c) < 1e-6:
            max_c += 1.0
        min_p, max_p = min(prices), max(prices)
        if abs(max_p - min_p) < 1e-6:
            max_p += 1.0

        n = len(series)
        step_x = cw / max(n - 1, 1)

        # 绘制 Volume Z-Score 底部柱状图
        for i, (t_lbl, z_val) in enumerate(z_series):
            bx = pad_l + i * step_x - 10
            bh = min(ch * 0.45, max(4.0, abs(z_val) * 18.0))
            by = pad_t + ch - bh
            b_col = QColor(250, 204, 21, 140) if z_val >= 2.0 else QColor(56, 189, 248, 70)
            painter.fillRect(QRectF(bx, by, 20, bh), b_col)
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(QRectF(bx - 12, pad_t + ch + 4, 44, 18), Qt.AlignCenter, t_lbl)

        # 绘制 CVD 曲线 (青绿) 与 Price 曲线 (亮金)
        cvd_pts = []
        price_pts = []
        for i, (_, c_val, p_val) in enumerate(series):
            px = pad_l + i * step_x
            cy = pad_t + ch - ((c_val - min_c) / (max_c - min_c)) * ch
            py = pad_t + ch - ((p_val - min_p) / (max_p - min_p)) * ch
            cvd_pts.append(QPointF(px, cy))
            price_pts.append(QPointF(px, py))

        painter.setPen(QPen(QColor("#10B981"), 2.4))
        for i in range(n - 1):
            painter.drawLine(cvd_pts[i], cvd_pts[i + 1])

        painter.setPen(QPen(QColor("#FACC15"), 2.0, Qt.DashLine))
        for i in range(n - 1):
            painter.drawLine(price_pts[i], price_pts[i + 1])

        # 左右双坐标轴刻度
        painter.setPen(QColor("#10B981"))
        painter.drawText(4, pad_t + 10, f"{max_c:+.0f}")
        painter.drawText(4, pad_t + ch, f"{min_c:+.0f}")
        painter.setPen(QColor("#FACC15"))
        painter.drawText(w - pad_r + 6, pad_t + 10, f"{max_p}")
        painter.drawText(w - pad_r + 6, pad_t + ch, f"{min_p}")

        if self.hover_x is not None and pad_l <= self.hover_x <= pad_l + cw:
            painter.setPen(QPen(QColor("#94A3B8"), 1, Qt.DotLine))
            painter.drawLine(int(self.hover_x), pad_t, int(self.hover_x), pad_t + ch)


# ---------------- 主窗口：OrderFlowScreenerMainWindow ----------------
class OrderFlowScreenerMainWindow(QMainWindow):
    def __init__(
        self,
        engine: OrderFlowEngine,
        ds_mgr: DataSourceManager,
        llm_mgr: LLMProviderManager,
        updater: AutoUpdater,
        icon_path: Optional[str] = None,
        local_api_port: int = 8787,
    ):
        super().__init__()
        self.engine = engine
        self.ds_mgr = ds_mgr
        self.llm_mgr = llm_mgr
        self.updater = updater
        self.icon_path = icon_path or ""
        self.local_api_port = local_api_port
        self._force_quit = False
        self._llm_worker: Optional[LLMStreamWorker] = None
        self._ds_worker: Optional[DataSourceProbeWorker] = None

        self.setWindowTitle(
            f"Order Flow Screener 订单流微观结构量化终端 {APP_VERSION} (全中文原生桌面版 | 本地API 127.0.0.1:{self.local_api_port})"
        )
        self.resize(1540, 940)
        self.setStyleSheet(DARK_STYLESHEET)

        if self.icon_path and os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        self._init_ui()
        self._init_system_tray()
        self._refresh_all_panels()

        # 实时行情与微观结构脉冲刷新定时器
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_auto_tick)
        self.refresh_timer.start(3500)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.icon_path and os.path.exists(self.icon_path):
            bind_win32_window_icon(int(self.winId()), self.icon_path)

    # ---------------- 系统托盘驻留 (QSystemTrayIcon) ----------------
    def _init_system_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return
        self.tray_icon = QSystemTrayIcon(self)
        if self.icon_path and os.path.exists(self.icon_path):
            self.tray_icon.setIcon(QIcon(self.icon_path))
        self.tray_icon.setToolTip(f"Order Flow Screener 订单流量化终端 {APP_VERSION}")

        tray_menu = QMenu(self)
        act_show = QAction("显示主终端窗口", self)
        act_show.triggered.connect(self.showNormal)
        act_refresh = QAction("立即刷新行情快照", self)
        act_refresh.triggered.connect(lambda: self._on_manual_refresh(try_rest=True))
        act_quit = QAction("彻底退出程序", self)
        act_quit.triggered.connect(self._quit_application)

        tray_menu.addAction(act_show)
        tray_menu.addAction(act_refresh)
        tray_menu.addSeparator()
        tray_menu.addAction(act_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()

    def _quit_application(self) -> None:
        self._force_quit = True
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if not self._force_quit and getattr(self, "chk_minimize_to_tray", None) and self.chk_minimize_to_tray.isChecked():
            if self.tray_icon and self.tray_icon.isVisible():
                self.hide()
                self.tray_icon.showMessage(
                    "Order Flow Screener 已最小化至系统托盘",
                    f"后台预警引擎与本地 API (127.0.0.1:{self.local_api_port}) 正在持续运行。",
                    QSystemTrayIcon.Information,
                    2500,
                )
                event.ignore()
                return
        event.accept()

    # ---------------- 构建全中文主界面架构 ----------------
    def _init_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(8)

        # 1. 顶部全局市场控制栏 (TopBar)
        root_layout.addWidget(self._build_top_control_bar())

        # 2. 单行全量核心 KPI 状态带 (Session Hero & KPI Strip)
        root_layout.addWidget(self._build_kpi_strip_card())

        # 3. 8 大核心功能主选项卡工作区
        self.main_tabs = QTabWidget(self)
        self.main_tabs.addTab(self._build_tab_footprint_terminal(), "📊 1. 足迹图与热力图主终端")
        self.main_tabs.addTab(self._build_tab_venues_and_levels(), "🌐 2. 跨所领涨对比与前日/裸POC")
        self.main_tabs.addTab(self._build_tab_derivatives_and_vol(), "⚡ 3. 衍生品持仓四象限与强平爆仓")
        self.main_tabs.addTab(self._build_tab_alerts_replay_export(), "🔔 4. 智能预警・录制回放・数据导出")
        self.main_tabs.addTab(self._build_tab_ai_microstructure(), "🤖 5. AI 订单流解读与本地/云端大模型")
        self.main_tabs.addTab(self._build_tab_datasources(), "🔌 6. 数据源接口管理中心 (12交易所+FX)")
        self.main_tabs.addTab(self._build_tab_autoupdate(), "🚀 7. 自动更新与上游同步中心")
        root_layout.addWidget(self.main_tabs, stretch=1)

        # 4. 底部状态条 (StatusBar)
        root_layout.addWidget(self._build_bottom_status_bar())

    def _build_top_control_bar(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("TopControlCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        lbl_brand = QLabel("📈 Order Flow 订单流终端 v2.3")
        lbl_brand.setObjectName("SectionHeader")
        layout.addWidget(lbl_brand)

        # 资产类别切换 (加密货币 / 外汇)
        layout.addWidget(QLabel("资产:"))
        self.cmb_asset = QComboBox()
        self.cmb_asset.addItems(["加密货币 (Crypto)", "外汇货币对 (Forex / OANDA)"])
        self.cmb_asset.currentIndexChanged.connect(self._on_asset_changed)
        layout.addWidget(self.cmb_asset)

        # 市场类型 (永续 / 现货)
        layout.addWidget(QLabel("市场:"))
        self.cmb_market = QComboBox()
        self.cmb_market.addItems(["永续合约 (Perpetual)", "现货市场 (Spot)"])
        self.cmb_market.currentIndexChanged.connect(self._on_market_changed)
        layout.addWidget(self.cmb_market)

        # 交易标的品种
        layout.addWidget(QLabel("标的:"))
        self.cmb_symbol = QComboBox()
        self.cmb_symbol.addItems(CRYPTO_INSTRUMENTS)
        self.cmb_symbol.currentTextChanged.connect(self._on_symbol_changed)
        layout.addWidget(self.cmb_symbol)

        # 周期选择 (1m ~ 4h)
        layout.addWidget(QLabel("周期:"))
        self.cmb_timeframe = QComboBox()
        self.cmb_timeframe.addItems(["1m", "5m", "15m", "1h", "4h"])
        self.cmb_timeframe.currentTextChanged.connect(self._on_timeframe_changed)
        layout.addWidget(self.cmb_timeframe)

        # 足迹图单元格模式
        layout.addWidget(QLabel("足迹模式:"))
        self.cmb_cell_mode = QComboBox()
        self.cmb_cell_mode.addItems(["买×卖双列 (Bid × Ask)", "净差值 (Delta)", "成交总量 (Volume)"])
        self.cmb_cell_mode.currentIndexChanged.connect(self._on_cell_mode_changed)
        layout.addWidget(self.cmb_cell_mode)

        # 工作区预设
        layout.addWidget(QLabel("工作区预设:"))
        self.cmb_workspace = QComboBox()
        self.cmb_workspace.addItems(["订单流标准 (Order Flow)", "流动性热力 (Liquidity)", "波动率监控 (Volatility)"])
        self.cmb_workspace.currentIndexChanged.connect(self._on_workspace_preset_changed)
        layout.addWidget(self.cmb_workspace)

        # 热力图与微观结构快速开关
        self.chk_heatmap = QCheckBox("挂单热力图")
        self.chk_heatmap.setChecked(True)
        self.chk_heatmap.toggled.connect(self._on_toggle_indicators)
        layout.addWidget(self.chk_heatmap)

        self.chk_micro = QCheckBox("吸收(ABS)/冰山单")
        self.chk_micro.setChecked(True)
        self.chk_micro.toggled.connect(self._on_toggle_indicators)
        layout.addWidget(self.chk_micro)

        layout.addStretch(1)

        btn_refresh = QPushButton("🔄 实时刷新快照")
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(lambda: self._on_manual_refresh(try_rest=True))
        layout.addWidget(btn_refresh)

        btn_ai_quick = QPushButton("🤖 AI 一键诊断当前盘口")
        btn_ai_quick.setObjectName("SuccessBtn")
        btn_ai_quick.clicked.connect(self._trigger_quick_ai_analysis)
        layout.addWidget(btn_ai_quick)

        return card

    def _build_kpi_strip_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("KpiStripCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(18)

        self.lbl_hero_price = QLabel("94,250.0")
        self.lbl_hero_price.setObjectName("HeroPrice")
        layout.addWidget(self.lbl_hero_price)

        self.kpi_labels: Dict[str, QLabel] = {}
        kpi_defs = [
            ("range", "当日区间 (High/Low)"),
            ("vwap", "当日 VWAP (±1σ)"),
            ("poc_va", "POC & 70%价值区 (VAH/VAL)"),
            ("delta_buy", "累计 Delta & 主动买盘%"),
            ("obi", "订单簿失衡度 (OBI)"),
            ("oi_regime", "全网持仓 OI & 四象限状态"),
            ("funding_basis", "8h资金费率 & 期现基差"),
            ("vol_z_rv", "成交 Z-Score & 年化波动率"),
        ]
        for k_id, k_title in kpi_defs:
            box = QVBoxLayout()
            box.setSpacing(2)
            t_lbl = QLabel(k_title)
            t_lbl.setObjectName("KpiTitle")
            v_lbl = QLabel("--")
            v_lbl.setObjectName("KpiValue")
            box.addWidget(t_lbl)
            box.addWidget(v_lbl)
            layout.addLayout(box)
            self.kpi_labels[k_id] = v_lbl

        layout.addStretch(1)
        return card

    # ---------------- 选项卡 1：足迹图主画布 + 订单簿深度 + 逐笔成交 + 双轴 CVD ----------------
    def _build_tab_footprint_terminal(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal, page)

        # 左侧主区：上方足迹图画布 + 下方双轴 CVD/Z-Score 量化副图
        left_container = QWidget()
        left_vbox = QVBoxLayout(left_container)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self.footprint_canvas = FootprintCanvasWidget(self.engine, self)
        self.study_canvas = DualAxisStudyCanvas(self.engine, self)

        left_vbox.addWidget(self.footprint_canvas, stretch=7)
        left_vbox.addWidget(self.study_canvas, stretch=3)
        splitter.addWidget(left_container)

        # 右侧停靠栏：上方聚合订单簿阶梯 (Order Book & OBI) + 下方毫秒级逐笔成交 (Time & Sales)
        right_container = QFrame()
        right_container.setObjectName("SectionCard")
        right_vbox = QVBoxLayout(right_container)
        right_vbox.setContentsMargins(8, 8, 8, 8)
        right_vbox.setSpacing(6)

        lbl_ob = QLabel("📚 多所聚合订单簿阶梯 (Order Book Ladder & OBI 深度)")
        lbl_ob.setObjectName("SectionHeader")
        right_vbox.addWidget(lbl_ob)

        self.bar_obi = QProgressBar()
        self.bar_obi.setRange(0, 100)
        self.bar_obi.setValue(57)
        self.bar_obi.setFormat("买方挂单深度占比 57.0%  |  OBI = +0.140")
        right_vbox.addWidget(self.bar_obi)

        self.tbl_orderbook = QTableWidget(12, 6)
        self.tbl_orderbook.setHorizontalHeaderLabels([
            "累计买深", "买盘挂单", "买价 (Bid)", "卖价 (Ask)", "卖盘挂单", "累计卖深"
        ])
        self.tbl_orderbook.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_orderbook.verticalHeader().setVisible(False)
        self.tbl_orderbook.setAlternatingRowColors(True)
        right_vbox.addWidget(self.tbl_orderbook, stretch=5)

        lbl_ts = QLabel("⏱️ 毫秒级逐笔成交与大单/强平流 (Time & Sales Tape)")
        lbl_ts.setObjectName("SectionHeader")
        right_vbox.addWidget(lbl_ts)

        self.tbl_trades = QTableWidget(25, 6)
        self.tbl_trades.setHorizontalHeaderLabels([
            "时间 (UTC)", "交易所", "成交价", "数量", "名义金额($)", "主动方向 / 标记"
        ])
        self.tbl_trades.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_trades.verticalHeader().setVisible(False)
        self.tbl_trades.setAlternatingRowColors(True)
        right_vbox.addWidget(self.tbl_trades, stretch=5)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 68)
        splitter.setStretchFactor(1, 32)
        layout.addWidget(splitter)
        return page

    # ---------------- 选项卡 2：跨交易所对比 (Lead/Lag) 与前日关键位 / 7日裸 POC ----------------
    def _build_tab_venues_and_levels(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lbl_v = QLabel("🌐 跨交易所价格发现、成交份额与 250ms 步进领先/滞后相关性矩阵 (Venues Lead / Lag Study)")
        lbl_v.setObjectName("SectionHeader")
        layout.addWidget(lbl_v)

        self.tbl_venues = QTableWidget(6, 10)
        self.tbl_venues.setHorizontalHeaderLabels([
            "交易所名称", "最新价", "相对中位价差(bps)", "1分钟成交量", "成交份额(%)",
            "1分钟净Delta", "领先/滞后(ms)", "互相关系数", "持仓量 OI ($)", "8h资金费率 / 期现基差"
        ])
        self.tbl_venues.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_venues.verticalHeader().setVisible(False)
        self.tbl_venues.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_venues, stretch=6)

        lbl_p = QLabel("📏 前一交易日关键位 (pPOC / pVAH / pVAL / pVWAP) 与近 7 日未回补裸 POC (Naked POCs)")
        lbl_p.setObjectName("SectionHeader")
        layout.addWidget(lbl_p)

        self.tbl_prior_levels = QTableWidget(7, 4)
        self.tbl_prior_levels.setHorizontalHeaderLabels([
            "关键位标签", "价格水平", "相对当前价偏离", "微观结构交易含义"
        ])
        self.tbl_prior_levels.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_prior_levels.verticalHeader().setVisible(False)
        self.tbl_prior_levels.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_prior_levels, stretch=4)

        return page

    # ---------------- 选项卡 3：衍生品持仓四象限状态机、爆仓级联与波动率研究 ----------------
    def _build_tab_derivatives_and_vol(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_grid = QGridLayout()
        self.lbl_deriv_summary = QLabel()
        self.lbl_deriv_summary.setWordWrap(True)
        self.lbl_deriv_summary.setStyleSheet(
            "background-color:#131B2E; border:1px solid #38BDF8; border-radius:8px; padding:12px; font-size:13px;"
        )
        top_grid.addWidget(self.lbl_deriv_summary, 0, 0, 1, 2)
        layout.addLayout(top_grid)

        lbl_liq = QLabel("💥 全网永续合约分桶强平爆仓监控 (Binance / Bybit / OKX / Deribit 实时聚合)")
        lbl_liq.setObjectName("SectionHeader")
        layout.addWidget(lbl_liq)

        self.tbl_liquidations = QTableWidget(6, 5)
        self.tbl_liquidations.setHorizontalHeaderLabels([
            "时间分桶", "多头强平额 (Long Liq 主动卖)", "空头强平额 (Short Liq 主动买)", "净强平差额 ($)", "同期收盘价"
        ])
        self.tbl_liquidations.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_liquidations.verticalHeader().setVisible(False)
        self.tbl_liquidations.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_liquidations, stretch=1)

        return page

    # ---------------- 选项卡 4：9大智能预警规则、实时录制回放与 CSV/PNG/报告导出 ----------------
    def _build_tab_alerts_replay_export(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 左侧：9大预警规则配置表与实时触发日志
        left_card = QFrame()
        left_card.setObjectName("SectionCard")
        l_vbox = QVBoxLayout(left_card)

        lbl_a = QLabel("🔔 9大订单流微观结构智能预警引擎 (Alerts Engine)")
        lbl_a.setObjectName("SectionHeader")
        l_vbox.addWidget(lbl_a)

        self.tbl_alert_rules = QTableWidget(9, 3)
        self.tbl_alert_rules.setHorizontalHeaderLabels(["启用状态", "预警规则名称", "触发条件阈值"])
        self.tbl_alert_rules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_alert_rules.verticalHeader().setVisible(False)
        l_vbox.addWidget(self.tbl_alert_rules, stretch=4)

        lbl_log = QLabel("📜 实时预警触发流水日志")
        lbl_log.setObjectName("SectionHeader")
        l_vbox.addWidget(lbl_log)

        self.tbl_alert_logs = QTableWidget(15, 5)
        self.tbl_alert_logs.setHorizontalHeaderLabels(["触发时间", "级别", "规则名称", "触发价格", "微观结构详情"])
        self.tbl_alert_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_alert_logs.verticalHeader().setVisible(False)
        l_vbox.addWidget(self.tbl_alert_logs, stretch=5)

        layout.addWidget(left_card, stretch=6)

        # 右侧：市场流录制与虚拟时钟回放 + 全量 CSV/PNG/Markdown/HTML 导出
        right_card = QFrame()
        right_card.setObjectName("SectionCard")
        r_vbox = QVBoxLayout(right_card)

        lbl_rec = QLabel("🎬 实时市场流录制与虚拟时钟回放 (1× / 5× / 20× Replay)")
        lbl_rec.setObjectName("SectionHeader")
        r_vbox.addWidget(lbl_rec)

        rec_btn_row = QHBoxLayout()
        self.btn_rec_toggle = QPushButton("⏺ 开始录制当前市场流 (Rec)")
        self.btn_rec_toggle.setObjectName("DangerBtn")
        self.btn_rec_toggle.clicked.connect(self._on_toggle_recording)
        rec_btn_row.addWidget(self.btn_rec_toggle)

        self.cmb_replay_speed = QComboBox()
        self.cmb_replay_speed.addItems(["1× 原速回放", "5× 倍速回放", "20× 极速回放"])
        rec_btn_row.addWidget(self.cmb_replay_speed)

        btn_replay_step = QPushButton("⏩ 快进 +10s 虚拟时钟")
        btn_replay_step.clicked.connect(lambda: self._on_manual_refresh(try_rest=False))
        rec_btn_row.addWidget(btn_replay_step)
        r_vbox.addLayout(rec_btn_row)

        self.tbl_recordings = QTableWidget(5, 5)
        self.tbl_recordings.setHorizontalHeaderLabels(["录制会话ID", "品种", "周期", "分块时长(秒)", "状态"])
        self.tbl_recordings.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_recordings.verticalHeader().setVisible(False)
        r_vbox.addWidget(self.tbl_recordings, stretch=4)

        lbl_exp = QLabel("💾 数据与图表全格式导出中心 (CSV / PNG / Markdown / HTML)")
        lbl_exp.setObjectName("SectionHeader")
        r_vbox.addWidget(lbl_exp)

        btn_exp_csv = QPushButton("📄 导出足迹图档位与订单流明细 CSV (兼容原版格式)")
        btn_exp_csv.setObjectName("PrimaryBtn")
        btn_exp_csv.clicked.connect(self._on_export_csv)
        r_vbox.addWidget(btn_exp_csv)

        btn_exp_png = QPushButton("🖼️ 导出高清足迹图与副图合成快照 PNG")
        btn_exp_png.clicked.connect(self._on_export_png)
        r_vbox.addWidget(btn_exp_png)

        btn_exp_report = QPushButton("📑 导出完整订单流量化诊断报告 (Markdown + HTML)")
        btn_exp_report.setObjectName("SuccessBtn")
        btn_exp_report.clicked.connect(self._on_export_ai_report)
        r_vbox.addWidget(btn_exp_report)

        self.lbl_export_status = QLabel("就绪：支持一键导出 UTC 毫秒级 CSV、高清画布 PNG 与 AI 研判报告。")
        self.lbl_export_status.setWordWrap(True)
        self.lbl_export_status.setStyleSheet("color:#10B981; padding:6px;")
        r_vbox.addWidget(self.lbl_export_status)
        r_vbox.addStretch(1)

        layout.addWidget(right_card, stretch=4)
        return page

    # ---------------- 选项卡 5：AI 订单流流式解读 + 本地/云端大模型配置中心 ----------------
    def _build_tab_ai_microstructure(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 左侧：大模型服务商与本地免 Key 接口配置
        cfg_card = QFrame()
        cfg_card.setObjectName("SectionCard")
        c_vbox = QVBoxLayout(cfg_card)

        lbl_cfg = QLabel("⚙️ 本地免Key大模型 (Ollama/LM Studio/vLLM) 与云端 API 配置中心")
        lbl_cfg.setObjectName("SectionHeader")
        c_vbox.addWidget(lbl_cfg)

        c_vbox.addWidget(QLabel("选择大模型服务商:"))
        self.cmb_llm_provider = QComboBox()
        for pid, pcfg in self.llm_mgr.providers.items():
            self.cmb_llm_provider.addItem(f"{pcfg['name']} [{pid}]", pid)
        self.cmb_llm_provider.currentIndexChanged.connect(self._on_llm_provider_selected)
        c_vbox.addWidget(self.cmb_llm_provider)

        c_vbox.addWidget(QLabel("接口 Base URL (OpenAI 兼容端点):"))
        self.edt_llm_baseurl = QLineEdit()
        c_vbox.addWidget(self.edt_llm_baseurl)

        c_vbox.addWidget(QLabel("API Key (本地 Ollama / LM Studio / vLLM 免填):"))
        self.edt_llm_apikey = QLineEdit()
        self.edt_llm_apikey.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.edt_llm_apikey.setPlaceholderText("本地模型无需填写 Key；云端模型请粘贴 API Key")
        c_vbox.addWidget(self.edt_llm_apikey)

        c_vbox.addWidget(QLabel("模型名称 (Model ID):"))
        self.cmb_llm_model = QComboBox()
        self.cmb_llm_model.setEditable(True)
        c_vbox.addWidget(self.cmb_llm_model)

        btn_row = QHBoxLayout()
        btn_discover = QPushButton("🔍 自动探测本地模型")
        btn_discover.clicked.connect(self._on_discover_local_models)
        btn_row.addWidget(btn_discover)

        btn_test_llm = QPushButton("⚡ 测试连接")
        btn_test_llm.clicked.connect(self._on_test_llm_connection)
        btn_row.addWidget(btn_test_llm)

        btn_save_llm = QPushButton("💾 保存并设为默认")
        btn_save_llm.setObjectName("PrimaryBtn")
        btn_save_llm.clicked.connect(self._on_save_llm_config)
        btn_row.addWidget(btn_save_llm)
        c_vbox.addLayout(btn_row)

        self.lbl_llm_status = QLabel(
            f"本地 OpenAI 兼容网关已启动: http://127.0.0.1:{self.local_api_port}/v1/chat/completions"
        )
        self.lbl_llm_status.setWordWrap(True)
        self.lbl_llm_status.setStyleSheet("color:#38BDF8; padding:6px;")
        c_vbox.addWidget(self.lbl_llm_status)

        c_vbox.addWidget(QLabel("自定义附加提问 (可选):"))
        self.edt_custom_question = QLineEdit()
        self.edt_custom_question.setPlaceholderText("例如：结合当前 CVD 背离与 7日裸 POC，判断短线多空止损位...")
        c_vbox.addWidget(self.edt_custom_question)

        btn_run_ai = QPushButton("🚀 启动 AI 流式微观结构深度研判")
        btn_run_ai.setObjectName("SuccessBtn")
        btn_run_ai.clicked.connect(self._trigger_quick_ai_analysis)
        c_vbox.addWidget(btn_run_ai)
        c_vbox.addStretch(1)

        layout.addWidget(cfg_card, stretch=4)

        # 右侧：AI 流式输出面板
        out_card = QFrame()
        out_card.setObjectName("SectionCard")
        o_vbox = QVBoxLayout(out_card)

        lbl_out = QLabel("🧠 AI 订单流微观结构实时流式研判报告 (支持 Markdown / HTML 导出)")
        lbl_out.setObjectName("SectionHeader")
        o_vbox.addWidget(lbl_out)

        self.txt_ai_output = QTextEdit()
        self.txt_ai_output.setReadOnly(True)
        o_vbox.addWidget(self.txt_ai_output, stretch=1)

        layout.addWidget(out_card, stretch=6)
        self._on_llm_provider_selected()
        return page

    # ---------------- 选项卡 6：数据源接口管理中心 (12大加密货币与 Finnhub 外汇) ----------------
    def _build_tab_datasources(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        lbl_ds = QLabel("🔌 12大实时市场数据源接口管理中心 (双向同步 .env.local)")
        lbl_ds.setObjectName("SectionHeader")
        top_bar.addWidget(lbl_ds)

        top_bar.addStretch(1)
        top_bar.addWidget(QLabel("Finnhub 外汇 API Key (NEXT_PUBLIC_FINNHUB_API_KEY):"))
        self.edt_finnhub_key = QLineEdit(self.ds_mgr.sources.get("finnhub_forex", {}).get("api_key", ""))
        self.edt_finnhub_key.setPlaceholderText("输入 Finnhub API Key 以启用 OANDA 外汇实时流")
        self.edt_finnhub_key.setMinimumWidth(260)
        top_bar.addWidget(self.edt_finnhub_key)

        btn_save_ds = QPushButton("💾 保存配置并写入 .env.local")
        btn_save_ds.setObjectName("PrimaryBtn")
        btn_save_ds.clicked.connect(self._on_save_datasources)
        top_bar.addWidget(btn_save_ds)

        btn_probe_all = QPushButton("🌐 并发测试全部 12 家数据源连通性")
        btn_probe_all.setObjectName("SuccessBtn")
        btn_probe_all.clicked.connect(self._on_probe_all_datasources)
        top_bar.addWidget(btn_probe_all)
        layout.addLayout(top_bar)

        self.bar_ds_probe = QProgressBar()
        self.bar_ds_probe.setRange(0, 100)
        self.bar_ds_probe.setValue(100)
        self.bar_ds_probe.setFormat("数据源配置就绪 (点击右上角按钮可并发探测全部 12 家交易所网关延迟)")
        layout.addWidget(self.bar_ds_probe)

        self.tbl_datasources = QTableWidget(len(self.ds_mgr.sources), 6)
        self.tbl_datasources.setHorizontalHeaderLabels([
            "数据源名称", "市场类别", "WebSocket 实时流端点", "订单簿深度覆盖规格", "支持微观结构特性", "连通状态 / 延迟"
        ])
        self.tbl_datasources.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_datasources.verticalHeader().setVisible(False)
        self.tbl_datasources.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_datasources, stretch=1)

        return page

    # ---------------- 选项卡 7：自动更新与上游同步中心 ----------------
    def _build_tab_autoupdate(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("SectionCard")
        vbox = QVBoxLayout(card)

        lbl_up = QLabel("🚀 应用内自动更新、静默覆盖安装与上游 GitHub 自动同步中心")
        lbl_up.setObjectName("SectionHeader")
        vbox.addWidget(lbl_up)

        info_text = (
            f"• 当前客户端版本：{APP_VERSION} (纯原生 PySide6 全中文桌面安装版)\n"
            f"• 您的发布仓库 (Fork)：https://github.com/{self.updater.fork_repo}\n"
            f"• 上游源项目仓库 (Upstream)：https://github.com/{self.updater.upstream_repo}\n"
            f"• 安装包规范：仅构建并发布 Inno Setup 标准安装包 `OrderFlowScreener-Setup-win64.exe`（严禁单文件便携版）。\n"
            f"• 自动同步机制：GitHub Actions 每日定时拉取上游最新 Commit，自动保护全部中文 GUI、本地大模型与数据源模块，通过 `--mode self-test` 校验后自动发布新 Release。"
        )
        lbl_info = QLabel(info_text)
        lbl_info.setStyleSheet("line-height:150%; font-size:13px; color:#CBD5E1; padding:8px;")
        vbox.addWidget(lbl_info)

        btn_row = QHBoxLayout()
        btn_check_up = QPushButton("🔍 立即检查 GitHub Releases 最新版本")
        btn_check_up.setObjectName("PrimaryBtn")
        btn_check_up.clicked.connect(self._on_check_updates)
        btn_row.addWidget(btn_check_up)

        btn_install_up = QPushButton("⚡ 一键下载并静默覆盖升级 (/VERYSILENT)")
        btn_install_up.setObjectName("SuccessBtn")
        btn_install_up.clicked.connect(self._on_install_update)
        btn_row.addWidget(btn_install_up)

        self.chk_minimize_to_tray = QCheckBox("关闭主窗口时最小化至 Windows 系统托盘后台运行")
        self.chk_minimize_to_tray.setChecked(True)
        btn_row.addWidget(self.chk_minimize_to_tray)
        btn_row.addStretch(1)
        vbox.addLayout(btn_row)

        self.bar_update_progress = QProgressBar()
        self.bar_update_progress.setRange(0, 100)
        self.bar_update_progress.setValue(0)
        vbox.addWidget(self.bar_update_progress)

        self.txt_update_log = QTextEdit()
        self.txt_update_log.setReadOnly(True)
        self.txt_update_log.setPlainText(
            "点击上方“立即检查 GitHub Releases 最新版本”可对比您的 Fork 仓库与上游 zadescoxp/order-flow-screener 最新版本。"
        )
        vbox.addWidget(self.txt_update_log, stretch=1)

        layout.addWidget(card)
        return page

    def _build_bottom_status_bar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("KpiStripCard")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 4, 12, 4)

        self.lbl_status_feed = QLabel(
            f"🟢 实时订单流引擎在线 | 本地 OpenAI 兼容网关: http://127.0.0.1:{self.local_api_port} | 默认模型: {self.llm_mgr.active_provider_id}/{self.llm_mgr.active_model}"
        )
        layout.addWidget(self.lbl_status_feed)
        layout.addStretch(1)
        self.lbl_status_clock = QLabel()
        layout.addWidget(self.lbl_status_clock)
        return bar

    # ---------------- 数据刷新与事件响应 ----------------
    def _refresh_all_panels(self) -> None:
        e = self.engine
        self.lbl_hero_price.setText(f"{e.symbol}  {e.last_price}")
        self.kpi_labels["range"].setText(f"{e.session_low} ~ {e.session_high}")
        self.kpi_labels["vwap"].setText(f"{e.session_vwap} (±{e.session_vwap_std})")
        self.kpi_labels["poc_va"].setText(f"POC {e.session_poc} | {e.session_val}~{e.session_vah}")
        self.kpi_labels["delta_buy"].setText(f"{e.session_delta:+.1f} (买盘 {e.buy_share_pct}%)")
        self.kpi_labels["obi"].setText(f"{e.obi_value:+.3f}")
        self.kpi_labels["oi_regime"].setText(f"${e.total_open_interest_usd/1e9:.2f}B | {e.positioning_regime.split(' ')[0]}")
        self.kpi_labels["funding_basis"].setText(f"{e.weighted_funding_8h_pct:+.4f}% | {e.mark_index_basis_bps:+.1f} bps")
        self.kpi_labels["vol_z_rv"].setText(f"Z={e.current_vol_zscore:+.2f}σ | RV={e.realized_vol_annual_pct:.1f}%")

        # 刷新足迹图与双轴副图画布
        self.footprint_canvas.update()
        self.study_canvas.update()

        # 刷新订单簿阶梯
        bid_pct = int(round((e.obi_value + 1.0) * 50.0))
        self.bar_obi.setValue(max(0, min(100, bid_pct)))
        self.bar_obi.setFormat(f"买方挂单深度占比 {bid_pct}%  |  OBI = {e.obi_value:+.3f}")

        n_ob = min(len(e.order_book_bids), len(e.order_book_asks))
        self.tbl_orderbook.setRowCount(n_ob)
        for r in range(n_ob):
            bp, bsz, bcum = e.order_book_bids[r]
            ap, asz, acum = e.order_book_asks[r]
            vals = [f"{bcum:.1f}", f"{bsz:.2f}", f"{bp}", f"{ap}", f"{asz:.2f}", f"{acum:.1f}"]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c_i == 2:
                    item.setForeground(QColor("#10B981"))
                elif c_i == 3:
                    item.setForeground(QColor("#F43F5E"))
                self.tbl_orderbook.setItem(r, c_i, item)

        # 刷新毫秒级逐笔成交
        self.tbl_trades.setRowCount(len(e.time_and_sales))
        for r, tr in enumerate(e.time_and_sales):
            vals = [
                tr["time"],
                tr["venue"],
                str(tr["price"]),
                str(tr["size"]),
                f"${tr['notional_usd']:,.1f}",
                f"{tr['side']} · {tr['tag']}",
            ]
            is_buy = "买入" in tr["side"]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if "强平" in tr["tag"] or "机构大单" in tr["tag"]:
                    item.setForeground(QColor("#FACC15"))
                elif c_i in (2, 5):
                    item.setForeground(QColor("#10B981") if is_buy else QColor("#F43F5E"))
                self.tbl_trades.setItem(r, c_i, item)

        # 刷新跨交易所对比表
        self.tbl_venues.setRowCount(len(e.venue_metrics))
        for r, vm in enumerate(e.venue_metrics):
            lag_txt = f"领先 +{vm.lead_lag_ms} ms ★" if vm.lead_lag_ms > 0 else f"{vm.lead_lag_ms} ms"
            vals = [
                vm.venue_name,
                str(vm.last_price),
                f"{vm.spread_bps_vs_median:+.2f} bps",
                f"{vm.volume_1m:,.1f}",
                f"{vm.volume_share_pct:.1f}%",
                f"{vm.delta_1m:+,.1f}",
                lag_txt,
                f"{vm.correlation:.3f}",
                f"${vm.open_interest_usd:,.0f}",
                f"{vm.funding_rate_8h_pct:+.4f}% / {vm.basis_bps:+.1f} bps",
            ]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c_i == 6 and vm.lead_lag_ms > 0:
                    item.setForeground(QColor("#FACC15"))
                self.tbl_venues.setItem(r, c_i, item)

        # 刷新前日关键位与7日裸 POC
        rows_levels = []
        for k, v in e.prior_levels.items():
            diff_bps = round((e.last_price - v) / max(v, 1e-6) * 10000.0, 2)
            rows_levels.append((k, str(v), f"{diff_bps:+.2f} bps", "昨日 5m K线精确合成价值区边界"))
        for npoc in e.naked_pocs:
            rows_levels.append((npoc["tag"], str(npoc["price"]), f"{npoc['distance_bps']:+.2f} bps", npoc["status"]))
        self.tbl_prior_levels.setRowCount(len(rows_levels))
        for r, row_data in enumerate(rows_levels):
            for c_i, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_prior_levels.setItem(r, c_i, item)

        # 刷新衍生品持仓四象限与强平分桶
        self.lbl_deriv_summary.setText(
            f"📌 【衍生品持仓四象限状态机】当前状态：{e.positioning_regime}  |  "
            f"全网聚合持仓量 (OI)：${e.total_open_interest_usd:,.0f} (5分钟变动 {e.oi_change_5m_pct:+.2f}%)  |  "
            f"OI加权8小时资金费率：{e.weighted_funding_8h_pct:+.4f}% (距下次结算 {e.next_funding_countdown})  |  "
            f"标记/指数期现基差：{e.mark_index_basis_bps:+.2f} bps\n"
            f"⚡ 【强平爆仓与波动率监控】5分钟多单强平：${e.liq_5m_long_usd:,.0f}  |  5分钟空单强平：${e.liq_5m_short_usd:,.0f}  |  "
            f"爆仓状态：{e.liq_state}  |  最大单笔爆仓：{e.largest_liq_desc}  |  "
            f"年化已实现波动率(RV)：{e.realized_vol_annual_pct}% ({e.vol_regime})  |  ATR(14)：{e.atr_14}  |  Parkinson波动率：{e.parkinson_vol_pct}%"
        )
        self.tbl_liquidations.setRowCount(len(e.liquidation_buckets))
        for r, lb in enumerate(e.liquidation_buckets):
            vals = [
                lb["time"],
                f"${lb['long_liq_usd']:,.0f}",
                f"${lb['short_liq_usd']:,.0f}",
                f"${lb['net_liq_usd']:+,.0f}",
                str(lb["price"]),
            ]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_liquidations.setItem(r, c_i, item)

        # 刷新预警规则与流水日志
        self.tbl_alert_rules.setRowCount(len(e.alert_rules))
        for r, (rid, rcfg) in enumerate(e.alert_rules.items()):
            vals = ["✅ 已启用" if rcfg["enabled"] else "⏸ 已暂停", rcfg["name"], rcfg["threshold"]]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_alert_rules.setItem(r, c_i, item)

        self.tbl_alert_logs.setRowCount(len(e.alerts_log))
        for r, al in enumerate(e.alerts_log):
            vals = [al.timestamp, al.severity, al.rule_name_cn, str(al.price), al.detail]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if c_i < 4 else Qt.AlignLeft | Qt.AlignVCenter)
                if al.severity == "CRITICAL":
                    item.setForeground(QColor("#F43F5E"))
                elif al.severity == "WARN":
                    item.setForeground(QColor("#FACC15"))
                self.tbl_alert_logs.setItem(r, c_i, item)

        # 刷新数据源表
        self._refresh_datasources_table()

        self.lbl_status_clock.setText(
            f"UTC 时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}  |  吞吐率: {e.trades_per_sec} 笔/秒"
        )

    def _refresh_datasources_table(self, probe_results: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        sources = list(self.ds_mgr.sources.values())
        self.tbl_datasources.setRowCount(len(sources))
        for r, scfg in enumerate(sources):
            sid = scfg["id"]
            p_res = (probe_results or {}).get(sid)
            if p_res:
                status_txt = f"🟢 {p_res['message']}" if p_res["ok"] else f"🟡 {p_res['message']}"
            else:
                status_txt = "🟢 已启用 (免Key直连)" if not scfg["requires_key"] else (
                    "🟢 已配置 Key" if scfg.get("api_key") else "⚪ 待填写 Finnhub Key"
                )
            vals = [
                scfg["name"],
                scfg["category"],
                scfg["ws_endpoint"],
                scfg["depth_reach"],
                "、".join(scfg["capabilities"][:3]),
                status_txt,
            ]
            for c_i, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if c_i in (1, 5) else Qt.AlignLeft | Qt.AlignVCenter)
                self.tbl_datasources.setItem(r, c_i, item)

    # ---------------- 交互回调槽函数 ----------------
    def _on_auto_tick(self) -> None:
        self.engine.rebuild_market_snapshot(try_live_rest=False)
        self._refresh_all_panels()

    def _on_manual_refresh(self, try_rest: bool = True) -> None:
        self.engine.rebuild_market_snapshot(try_live_rest=try_rest)
        self._refresh_all_panels()

    def _on_asset_changed(self, idx: int) -> None:
        self.engine.asset_class = "CRYPTO" if idx == 0 else "FOREX"
        self.cmb_symbol.blockSignals(True)
        self.cmb_symbol.clear()
        if self.engine.asset_class == "CRYPTO":
            self.cmb_symbol.addItems(CRYPTO_INSTRUMENTS)
            self.cmb_market.setEnabled(True)
        else:
            self.cmb_symbol.addItems(FOREX_INSTRUMENTS)
            self.cmb_market.setEnabled(False)
        self.cmb_symbol.blockSignals(False)
        self.engine.symbol = self.cmb_symbol.currentText()
        self._on_manual_refresh(try_rest=False)

    def _on_market_changed(self, idx: int) -> None:
        self.engine.market_type = "PERP" if idx == 0 else "SPOT"
        self._on_manual_refresh(try_rest=False)

    def _on_symbol_changed(self, sym: str) -> None:
        if sym:
            self.engine.symbol = sym
            self._on_manual_refresh(try_rest=False)

    def _on_timeframe_changed(self, tf: str) -> None:
        if tf:
            self.engine.timeframe = tf
            self._on_manual_refresh(try_rest=False)

    def _on_cell_mode_changed(self, idx: int) -> None:
        modes = ["BID_ASK", "DELTA", "VOLUME"]
        self.engine.cell_mode = modes[idx] if 0 <= idx < len(modes) else "BID_ASK"
        self.footprint_canvas.update()

    def _on_workspace_preset_changed(self, idx: int) -> None:
        if idx == 0:
            self.main_tabs.setCurrentIndex(0)
        elif idx == 1:
            self.chk_heatmap.setChecked(True)
            self.main_tabs.setCurrentIndex(0)
        elif idx == 2:
            self.main_tabs.setCurrentIndex(2)

    def _on_toggle_indicators(self) -> None:
        self.engine.show_resting_heatmap = self.chk_heatmap.isChecked()
        self.engine.show_microstructure = self.chk_micro.isChecked()
        self.footprint_canvas.update()

    def _on_toggle_recording(self) -> None:
        if not self.engine.is_recording:
            msg = self.engine.start_recording()
            self.btn_rec_toggle.setText("⏹ 停止录制并保存会话")
            self.lbl_export_status.setText(msg)
        else:
            meta = self.engine.stop_recording()
            self.btn_rec_toggle.setText("⏺ 开始录制当前市场流 (Rec)")
            self.lbl_export_status.setText(f"已保存录制会话 {meta['session_id']} ({meta['duration_sec']} 秒)")
            self.tbl_recordings.setRowCount(len(self.engine.recorded_sessions))
            for r, rec in enumerate(self.engine.recorded_sessions):
                vals = [rec["session_id"], rec["symbol"], rec["timeframe"], str(rec["duration_sec"]), rec["status"]]
                for c_i, val in enumerate(vals):
                    self.tbl_recordings.setItem(r, c_i, QTableWidgetItem(val))

    def _on_export_csv(self) -> None:
        out_dir = Path.home() / "Desktop"
        if not out_dir.exists():
            out_dir = Path.cwd()
        target = out_dir / f"OrderFlow_{self.engine.symbol}_{self.engine.timeframe}_{int(time.time())}.csv"
        saved = self.engine.export_footprint_csv(target)
        self.lbl_export_status.setText(f"✅ 已导出足迹图与档位明细 CSV 至：{saved}")

    def _on_export_png(self) -> None:
        out_dir = Path.home() / "Desktop"
        if not out_dir.exists():
            out_dir = Path.cwd()
        target = out_dir / f"OrderFlow_Chart_{self.engine.symbol}_{int(time.time())}.png"
        pix = self.footprint_canvas.grab()
        pix.save(str(target), "PNG")
        self.lbl_export_status.setText(f"✅ 已导出高清足迹图快照 PNG 至：{target}")

    def _on_export_ai_report(self) -> None:
        out_dir = Path.home() / "Desktop"
        if not out_dir.exists():
            out_dir = Path.cwd()
        md_path = out_dir / f"OrderFlow_AI_Report_{self.engine.symbol}_{int(time.time())}.md"
        html_path = md_path.with_suffix(".html")
        content = self.txt_ai_output.toPlainText().strip()
        if not content:
            content = self.llm_mgr.chat_completion(self.engine.build_ai_prompt_context())
            self.txt_ai_output.setPlainText(content)
        md_path.write_text(content, encoding="utf-8")
        html_body = (
            f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            f"<title>{self.engine.symbol} 订单流微观结构量化报告</title>"
            f"<style>body{{background:#0B101E;color:#E2E8F0;font-family:'Microsoft YaHei',sans-serif;padding:32px;line-height:1.7;}}"
            f"pre{{background:#131B2E;padding:16px;border-radius:8px;border:1px solid #38BDF8;white-space:pre-wrap;}}</style></head>"
            f"<body><h2>{self.engine.symbol} ({self.engine.timeframe}) 订单流微观结构量化诊断报告</h2>"
            f"<pre>{content}</pre></body></html>"
        )
        html_path.write_text(html_body, encoding="utf-8")
        self.lbl_export_status.setText(f"✅ 已导出 Markdown 与 HTML 报告至：{md_path.name} / {html_path.name}")

    # ---------------- AI 大模型配置与流式分析 ----------------
    def _on_llm_provider_selected(self) -> None:
        pid = self.cmb_llm_provider.currentData()
        if not pid:
            return
        pcfg = self.llm_mgr.providers.get(pid, {})
        self.edt_llm_baseurl.setText(pcfg.get("base_url", ""))
        self.edt_llm_apikey.setText(pcfg.get("api_key", ""))
        self.cmb_llm_model.clear()
        self.cmb_llm_model.addItems(pcfg.get("models", []))
        self.cmb_llm_model.setCurrentText(pcfg.get("default_model", ""))

    def _on_discover_local_models(self) -> None:
        pid = self.cmb_llm_provider.currentData()
        models = self.llm_mgr.discover_local_models(pid)
        self.cmb_llm_model.clear()
        self.cmb_llm_model.addItems(models)
        self.lbl_llm_status.setText(f"✅ 已完成 {pid} 模型探测，共发现 {len(models)} 个模型。")

    def _on_test_llm_connection(self) -> None:
        self._on_save_llm_config()
        pid = self.cmb_llm_provider.currentData()
        res = self.llm_mgr.test_connection(pid)
        self.lbl_llm_status.setText(res["message"])

    def _on_save_llm_config(self) -> None:
        pid = self.cmb_llm_provider.currentData()
        if not pid:
            return
        self.llm_mgr.update_provider(
            provider_id=pid,
            base_url=self.edt_llm_baseurl.text(),
            api_key=self.edt_llm_apikey.text(),
            default_model=self.cmb_llm_model.currentText(),
            set_active=True,
        )
        self.lbl_llm_status.setText(
            f"✅ 已保存并激活模型：{pid} / {self.llm_mgr.active_model}"
        )

    def _trigger_quick_ai_analysis(self) -> None:
        self.main_tabs.setCurrentIndex(4)
        self._on_save_llm_config()
        ctx = self.engine.build_ai_prompt_context()
        extra = self.edt_custom_question.text().strip()
        if extra:
            ctx += f"\n\n【用户重点关注问题】\n{extra}"
        self.txt_ai_output.clear()
        self.lbl_llm_status.setText(
            f"⏳ 正在通过 {self.llm_mgr.active_provider_id}/{self.llm_mgr.active_model} 流式生成订单流微观结构研判..."
        )
        self._llm_worker = LLMStreamWorker(self.llm_mgr, ctx)
        self._llm_worker.token_received.connect(self._on_ai_stream_chunk)
        self._llm_worker.finished_full.connect(
            lambda _: self.lbl_llm_status.setText("✅ AI 订单流微观结构流式研判已完成。")
        )
        self._llm_worker.start()

    def _on_ai_stream_chunk(self, chunk: str) -> None:
        cursor = self.txt_ai_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.txt_ai_output.setTextCursor(cursor)

    # ---------------- 数据源保存与并发连通性测试 ----------------
    def _on_save_datasources(self) -> None:
        fkey = self.edt_finnhub_key.text().strip()
        self.ds_mgr.update_source("finnhub_forex", enabled=True, api_key=fkey)
        self.bar_ds_probe.setFormat("✅ 已保存 Finnhub 外汇密钥并同步更新 .env.local 配置文件")

    def _on_probe_all_datasources(self) -> None:
        self._on_save_datasources()
        self.bar_ds_probe.setValue(0)
        self.bar_ds_probe.setFormat("正在并发探测全部 12 家交易所与 Finnhub 网关延迟...")
        self._probe_map: Dict[str, Dict[str, Any]] = {}
        self._ds_worker = DataSourceProbeWorker(self.ds_mgr)
        self._ds_worker.progress_updated.connect(self._on_ds_probe_step)
        self._ds_worker.all_completed.connect(self._on_ds_probe_done)
        self._ds_worker.start()

    def _on_ds_probe_step(self, pct: int, sid: str, res: dict) -> None:
        self._probe_map[sid] = res
        self.bar_ds_probe.setValue(pct)
        self.bar_ds_probe.setFormat(f"已探测 {sid}: {res['message']} ({pct}%)")
        self._refresh_datasources_table(self._probe_map)

    def _on_ds_probe_done(self, results: list) -> None:
        ok_cnt = sum(1 for r in results if r.get("ok"))
        self.bar_ds_probe.setValue(100)
        self.bar_ds_probe.setFormat(f"✅ 12 家数据源并发探测完毕：{ok_cnt}/{len(results)} 个网关直接响应")

    # ---------------- 自动更新检查与静默安装 ----------------
    def _on_check_updates(self) -> None:
        info = self.updater.check_for_updates()
        self.txt_update_log.setPlainText(json.dumps(info, ensure_ascii=False, indent=2))
        self.bar_update_progress.setValue(100)
        self.bar_update_progress.setFormat(info["status_message"])

    def _on_install_update(self) -> None:
        info = self.updater.check_for_updates()
        res = self.updater.download_and_install_update(
            info.get("download_url", ""),
            silent=True,
            progress_callback=lambda pct, msg: (
                self.bar_update_progress.setValue(pct),
                self.bar_update_progress.setFormat(msg),
            ),
        )
        self.txt_update_log.append(f"\n[自动升级结果] {res['message']}")


def launch_gui_app(
    engine: OrderFlowEngine,
    ds_mgr: DataSourceManager,
    llm_mgr: LLMProviderManager,
    updater: AutoUpdater,
    icon_path: Optional[str] = None,
    local_api_port: int = 8787,
) -> int:
    setup_windows_hidpi_and_appid()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("OrderFlowScreener-CN")
    app.setOrganizationName("gouqizi2214730-source")
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    win = OrderFlowScreenerMainWindow(
        engine=engine,
        ds_mgr=ds_mgr,
        llm_mgr=llm_mgr,
        updater=updater,
        icon_path=icon_path,
        local_api_port=local_api_port,
    )
    win.show()
    return app.exec()
