#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 OpenAI 兼容 HTTP API 后台守护服务 (local_api_server.py)
默认监听 http://127.0.0.1:8787，提供：
- GET  /health               -> 健康检查与版本信息
- GET  /v1/models            -> 暴露已连接的本地/云端大模型及内置 `order-flow-microstructure-agent`
- POST /v1/chat/completions  -> OpenAI 兼容对话接口（自动注入当前实时订单流足迹图/CVD/OBI/OI 微观结构快照）
- GET  /api/providers        -> 获取所有本地/云端大模型服务商配置
- GET  /api/datasources      -> 获取全部 12 家加密货币与外汇数据源状态
- GET  /api/snapshot         -> 获取当前品种完整订单流指标 JSON 快照
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Any


class LocalAPIRequestHandler(BaseHTTPRequestHandler):
    engine: Any = None
    llm_mgr: Any = None
    ds_mgr: Any = None

    def log_message(self, format: str, *args: Any) -> None:
        # 禁用控制台标准错误打印，防止无控制台模式下句柄异常
        pass

    def _send_json(self, status_code: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            self._send_json(200, {
                "status": "ok",
                "app": "OrderFlowScreener-CN",
                "version": "v2.3.0",
                "upstream": "zadescoxp/order-flow-screener",
                "fork": "gouqizi2214730-source/order-flow-screener",
                "active_symbol": getattr(self.engine, "symbol", "BTCUSDT"),
                "active_llm": f"{self.llm_mgr.active_provider_id}/{self.llm_mgr.active_model}",
            })
            return

        if self.path.startswith("/v1/models"):
            models_data = [
                {
                    "id": "order-flow-microstructure-agent",
                    "object": "model",
                    "created": 1732180000,
                    "owned_by": "order-flow-screener-cn",
                }
            ]
            for pid, pcfg in self.llm_mgr.providers.items():
                for m in pcfg.get("models", []):
                    models_data.append({
                        "id": f"{pid}/{m}",
                        "object": "model",
                        "created": 1732180000,
                        "owned_by": pid,
                    })
            self._send_json(200, {"object": "list", "data": models_data})
            return

        if self.path.startswith("/api/providers"):
            self._send_json(200, {
                "active_provider_id": self.llm_mgr.active_provider_id,
                "active_model": self.llm_mgr.active_model,
                "providers": self.llm_mgr.providers,
            })
            return

        if self.path.startswith("/api/datasources"):
            self._send_json(200, {
                "site_url": self.ds_mgr.site_url,
                "proxy_url": self.ds_mgr.proxy_url,
                "sources": self.ds_mgr.sources,
            })
            return

        if self.path.startswith("/api/snapshot"):
            self._send_json(200, {
                "symbol": self.engine.symbol,
                "asset_class": self.engine.asset_class,
                "market_type": self.engine.market_type,
                "timeframe": self.engine.timeframe,
                "last_price": self.engine.last_price,
                "session_vwap": self.engine.session_vwap,
                "session_poc": self.engine.session_poc,
                "session_vah": self.engine.session_vah,
                "session_val": self.engine.session_val,
                "session_volume": self.engine.session_volume,
                "session_delta": self.engine.session_delta,
                "obi": self.engine.obi_value,
                "vol_zscore": self.engine.current_vol_zscore,
                "realized_vol_pct": self.engine.realized_vol_annual_pct,
                "positioning_regime": self.engine.positioning_regime,
                "prior_levels": self.engine.prior_levels,
                "naked_pocs": self.engine.naked_pocs,
            })
            return

        self._send_json(404, {"error": "Endpoint not found", "path": self.path})

    def do_POST(self) -> None:
        if self.path.startswith("/v1/chat/completions"):
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8", errors="ignore") if length > 0 else "{}"
            try:
                body = json.loads(raw_body)
            except Exception:
                body = {}
            messages = body.get("messages", [])
            user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            snapshot_ctx = self.engine.build_ai_prompt_context() if self.engine else ""
            combined_prompt = f"{snapshot_ctx}\n\n【用户分析请求】\n{user_msg or '请对当前标的执行完整的订单流与微观结构多空诊断。'}"
            answer = self.llm_mgr.chat_completion(combined_prompt)
            resp_payload = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", self.llm_mgr.active_model),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": answer},
                        "finish_reason": "stop",
                    }
                ],
            }
            self._send_json(200, resp_payload)
            return

        self._send_json(404, {"error": "POST endpoint not found"})


class LocalAPIServer:
    """后台守护线程运行 127.0.0.1:8787 OpenAI 兼容本地 API 网关"""

    def __init__(self, engine: Any, llm_mgr: Any, ds_mgr: Any, host: str = "127.0.0.1", port: int = 8787):
        self.engine = engine
        self.llm_mgr = llm_mgr
        self.ds_mgr = ds_mgr
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if self._server is not None:
            return True
        LocalAPIRequestHandler.engine = self.engine
        LocalAPIRequestHandler.llm_mgr = self.llm_mgr
        LocalAPIRequestHandler.ds_mgr = self.ds_mgr
        for try_port in (self.port, self.port + 1, self.port + 2):
            try:
                self._server = ThreadingHTTPServer((self.host, try_port), LocalAPIRequestHandler)
                self.port = try_port
                self._thread = threading.Thread(
                    target=self._server.serve_forever,
                    name="OrderFlowLocalAPIServer",
                    daemon=True,
                )
                self._thread.start()
                return True
            except OSError:
                continue
        return False

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
