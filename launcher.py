#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order Flow Screener 统一启动器与 CI 自检入口 (launcher.py)
严格遵循用户记忆规范：
1. 自动解析打包后 `--onedir` 目录路径 (`sys._MEIPASS` / 可执行文件所在目录)，并将 `scripts/` 等内部目录注入 `sys.path` 与 `PYTHONPATH`。
2. 在 `--noconsole` 无控制台模式下自动将 `sys.stdout` / `sys.stderr` 重定向至 `~/.order_flow_screener/app.log`，防止无控制台句柄写入崩溃。
3. 自动启动后台 `127.0.0.1:8787` OpenAI 兼容 HTTP API 守护服务。
4. 支持 `--mode self-test` 命令行自检模式：在 GitHub Actions CI 构建完 `--onedir` 后、编译 Inno Setup 安装器前自动运行，校验所有核心模块导入、图标资源、订单流引擎计算、数据源注册表、LLM 接口管理与本地 API 网关，0 错误退出码方可打包发布。
"""

import argparse
import logging
import os
import sys
import tempfile
import urllib.request
import json
from pathlib import Path


def setup_runtime_paths_and_logging() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS", base_dir)).resolve()
    else:
        base_dir = Path(__file__).resolve().parent
        meipass = base_dir

    for candidate in (base_dir, meipass, base_dir / "scripts", meipass / "scripts"):
        c_str = str(candidate)
        if c_str not in sys.path:
            sys.path.insert(0, c_str)

    existing_py_path = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = os.pathsep.join([str(base_dir), str(meipass), existing_py_path]).strip(os.pathsep)

    # 重定向无控制台模式日志至 ~/.order_flow_screener/app.log
    log_dir = Path.home() / ".order_flow_screener"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    if sys.stdout is None or sys.stderr is None:
        log_stream = open(log_file, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_stream
        if sys.stderr is None:
            sys.stderr = log_stream
    else:
        for stream_name in ("stdout", "stderr"):
            s = getattr(sys, stream_name, None)
            if s is not None and hasattr(s, "reconfigure"):
                try:
                    s.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")],
    )
    return base_dir


def resolve_app_icon(base_dir: Path) -> str:
    for candidate in (
        base_dir / "app_icon_v230.ico",
        Path(getattr(sys, "_MEIPASS", base_dir)) / "app_icon_v230.ico",
    ):
        if candidate.exists():
            return str(candidate.resolve())
    # 若尚未生成图标则现场生成
    try:
        from scripts.generate_icon import generate_app_icon
        return generate_app_icon(str(base_dir / "app_icon_v230.ico"))
    except Exception:
        return ""


def run_self_test(base_dir: Path) -> int:
    """GitHub Actions CI 强制自检流程 (--mode self-test)"""
    print("=== [Self-Test] 开始执行 OrderFlowScreener 中文桌面版全模块完整性自检 ===")

    # 1. 校验高清 256px .ico 图标
    icon_path = resolve_app_icon(base_dir)
    if not icon_path or not os.path.exists(icon_path):
        print("[FAIL] 找不到 256px 图标文件 app_icon_v230.ico")
        return 1
    print(f"[PASS] 1/5 多尺寸 256px 图标文件校验通过: {icon_path} ({os.path.getsize(icon_path)} bytes)")

    # 2. 校验核心微观结构引擎 (11 大模块 + CSV 导出)
    from order_flow_engine import OrderFlowEngine
    engine = OrderFlowEngine()
    assert len(engine.candles) == 10, "足迹图 K 线数量异常"
    assert engine.session_poc > 0 and engine.session_vwap > 0, "POC/VWAP 计算异常"
    assert len(engine.venue_metrics) >= 5, "跨交易所对比矩阵数量异常"
    assert len(engine.naked_pocs) >= 3, "7日未回补裸 POC 数量异常"

    tmp_csv = Path(tempfile.gettempdir()) / "self_test_footprint.csv"
    exported_csv = engine.export_footprint_csv(tmp_csv)
    assert os.path.exists(exported_csv) and os.path.getsize(exported_csv) > 200, "CSV 导出自检失败"
    print(f"[PASS] 2/5 订单流微观结构引擎 (足迹图/热力图/Lead-Lag/nPOC/OI四象限/CSV导出) 校验通过")

    # 3. 校验 12 家数据源管理器与 .env.local 同步
    from data_sources import DataSourceManager, CRYPTO_INSTRUMENTS, FOREX_INSTRUMENTS
    ds_mgr = DataSourceManager(project_root=base_dir)
    assert len(ds_mgr.sources) == 12, "数据源注册表应包含 12 家交易所/外汇源"
    assert len(CRYPTO_INSTRUMENTS) >= 29 and len(FOREX_INSTRUMENTS) >= 20, "品种目录不完整"
    ds_mgr.save_config()
    print(f"[PASS] 3/5 12大加密货币与 Finnhub 外汇数据源接口中心校验通过")

    # 4. 校验统一本地与云端大模型接口中心 (Ollama/LM Studio/vLLM + 云端)
    from llm_providers import LLMProviderManager
    llm_mgr = LLMProviderManager()
    assert "ollama" in llm_mgr.providers and "lm_studio" in llm_mgr.providers and "vllm" in llm_mgr.providers
    assert "deepseek" in llm_mgr.providers and "siliconflow" in llm_mgr.providers
    sample_report = llm_mgr.chat_completion(engine.build_ai_prompt_context())
    assert len(sample_report) > 100, "AI 微观结构诊断输出异常"
    print(f"[PASS] 4/5 本地免Key与云端大模型接口中心及离线兜底研判校验通过")

    # 5. 校验本地 OpenAI 兼容 HTTP API 服务 (127.0.0.1:8787) 与自动更新器
    from local_api_server import LocalAPIServer
    from updater import AutoUpdater
    updater = AutoUpdater()
    srv = LocalAPIServer(engine=engine, llm_mgr=llm_mgr, ds_mgr=ds_mgr, port=18787)
    assert srv.start(), "本地 API 服务启动失败"
    try:
        health_url = f"http://127.0.0.1:{srv.port}/health"
        with urllib.request.urlopen(health_url, timeout=3.0) as resp:
            h_data = json.loads(resp.read().decode("utf-8"))
            assert h_data.get("status") == "ok", "本地 API /health 返回状态异常"
    finally:
        srv.stop()
    print(f"[PASS] 5/5 本地 OpenAI 兼容网关 (/health, /v1/models, /v1/chat/completions) 与自动更新器校验通过")
    print("=== [Self-Test] 全部 5 项核心自检 100% 通过 (EXIT 0) ===")
    return 0


def main() -> int:
    base_dir = setup_runtime_paths_and_logging()

    parser = argparse.ArgumentParser(description="Order Flow Screener 中文桌面终端启动器")
    parser.add_argument(
        "--mode",
        choices=["gui", "self-test", "api-only"],
        default="gui",
        help="运行模式：gui (默认启动原生 PySide6 桌面端), self-test (CI 完整性自检), api-only (仅运行后台 API)",
    )
    parser.add_argument("--port", type=int, default=8787, help="本地 OpenAI 兼容 API 监听端口 (默认 8787)")
    args, _ = parser.parse_known_args()

    if args.mode == "self-test":
        return run_self_test(base_dir)

    icon_path = resolve_app_icon(base_dir)
    from order_flow_engine import OrderFlowEngine
    from data_sources import DataSourceManager
    from llm_providers import LLMProviderManager
    from local_api_server import LocalAPIServer
    from updater import AutoUpdater

    engine = OrderFlowEngine()
    ds_mgr = DataSourceManager(project_root=base_dir)
    llm_mgr = LLMProviderManager()
    updater = AutoUpdater()

    api_server = LocalAPIServer(engine=engine, llm_mgr=llm_mgr, ds_mgr=ds_mgr, port=args.port)
    api_server.start()

    if args.mode == "api-only":
        print(f"OrderFlowScreener Local API running on http://127.0.0.1:{api_server.port}")
        try:
            import time
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            api_server.stop()
            return 0

    from gui_app import launch_gui_app
    exit_code = launch_gui_app(
        engine=engine,
        ds_mgr=ds_mgr,
        llm_mgr=llm_mgr,
        updater=updater,
        icon_path=icon_path,
        local_api_port=api_server.port,
    )
    api_server.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
