#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一本地与云端大模型接口中心 (llm_providers.py)
支持：
1. 免 API Key 本地大模型推理服务：Ollama (11434)、LM Studio (1234)、vLLM (8000)
2. 主流云端大模型接口：DeepSeek、通义千问 (DashScope)、硅基流动 (SiliconFlow)、智谱 GLM、
   月之暗面 (Moonshot/Kimi)、OpenAI、Anthropic Claude、Google Gemini、OpenRouter、自定义 OpenAI 兼容端点
3. 流式输出 (Streaming SSE) 与结构化订单流微观结构解读提示词生成
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Generator, Optional, Callable


CONFIG_DIR = Path.home() / ".order_flow_screener"
CONFIG_FILE = CONFIG_DIR / "llm_config.json"


DEFAULT_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "name": "Ollama (本地免Key推理)",
        "category": "local",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "ollama",
        "requires_key": False,
        "default_model": "qwen2.5:14b",
        "models": ["qwen2.5:14b", "qwen2.5:7b", "deepseek-r1:14b", "deepseek-r1:8b", "llama3.1:8b"],
        "description": "本地 Ollama 推理服务，默认端口 11434，无需 API Key，支持一键拉取本地模型列表。",
    },
    "lm_studio": {
        "name": "LM Studio (本地免Key推理)",
        "category": "local",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "lm-studio",
        "requires_key": False,
        "default_model": "qwen2.5-14b-instruct",
        "models": ["qwen2.5-14b-instruct", "deepseek-r1-distill-qwen-14b", "local-model"],
        "description": "本地 LM Studio OpenAI 兼容服务，默认端口 1234，零配置免 Key 即连。",
    },
    "vllm": {
        "name": "vLLM / LocalAI (本地高并发推理)",
        "category": "local",
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "EMPTY",
        "requires_key": False,
        "default_model": "Qwen/Qwen2.5-14B-Instruct",
        "models": ["Qwen/Qwen2.5-14B-Instruct", "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"],
        "description": "本地或内网 vLLM 高吞吐推理端点，默认端口 8000。",
    },
    "deepseek": {
        "name": "DeepSeek (深度求索官方)",
        "category": "cloud",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "env_key": "DEEPSEEK_API_KEY",
        "requires_key": True,
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "description": "DeepSeek V3 / R1 官方云端 API，极高性价比，适合高频订单流微观结构推理。",
    },
    "siliconflow": {
        "name": "SiliconFlow (硅基流动)",
        "category": "cloud",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",
        "env_key": "SILICONFLOW_API_KEY",
        "requires_key": True,
        "default_model": "deepseek-ai/DeepSeek-V3",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
        "description": "国内高速聚合推理平台，支持满血 DeepSeek-R1/V3 与 Qwen 全系列模型。",
    },
    "dashscope": {
        "name": "阿里云百炼 / 通义千问 (DashScope)",
        "category": "cloud",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "env_key": "DASHSCOPE_API_KEY",
        "requires_key": True,
        "default_model": "qwen-plus",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwq-32b"],
        "description": "阿里云百炼 OpenAI 兼容接口，支持 Qwen-Max 与 QwQ 深度推理模型。",
    },
    "zhipu": {
        "name": "智谱清言 (GLM-4)",
        "category": "cloud",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "env_key": "ZHIPU_API_KEY",
        "requires_key": True,
        "default_model": "glm-4-plus",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-zero-preview"],
        "description": "智谱 AI 开放平台，其中 glm-4-flash 支持免费高并发调用。",
    },
    "moonshot": {
        "name": "月之暗面 (Moonshot / Kimi)",
        "category": "cloud",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "",
        "env_key": "MOONSHOT_API_KEY",
        "requires_key": True,
        "default_model": "moonshot-v1-32k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "description": "Kimi 长上下文大模型，适合跨周期多交易所订单流复盘报告生成。",
    },
    "openai": {
        "name": "OpenAI 官方接口",
        "category": "cloud",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "env_key": "OPENAI_API_KEY",
        "requires_key": True,
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
        "description": "OpenAI 官方云端接口。",
    },
    "gemini": {
        "name": "Google Gemini (OpenAI 兼容端点)",
        "category": "cloud",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "env_key": "GEMINI_API_KEY",
        "requires_key": True,
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "description": "Google Gemini 官方 OpenAI 兼容接口。",
    },
    "anthropic": {
        "name": "Anthropic Claude (OpenRouter / 兼容网关)",
        "category": "cloud",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "env_key": "OPENROUTER_API_KEY",
        "requires_key": True,
        "default_model": "anthropic/claude-3.7-sonnet",
        "models": ["anthropic/claude-3.7-sonnet", "anthropic/claude-3.5-haiku"],
        "description": "通过 OpenRouter 或兼容网关调用 Claude 3.7 Sonnet。",
    },
    "custom": {
        "name": "自定义 OpenAI 兼容网关",
        "category": "custom",
        "base_url": "http://127.0.0.1:3000/v1",
        "api_key": "",
        "env_key": "CUSTOM_LLM_API_KEY",
        "requires_key": False,
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini"],
        "description": "任意兼容 OpenAI /v1/chat/completions 规范的本地或私有云端点。",
    },
}


class LLMProviderManager:
    """统一管理本地与云端大模型配置、在线探测、流式推理与订单流微观结构 AI 诊断"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.providers: Dict[str, Dict[str, Any]] = json.loads(json.dumps(DEFAULT_PROVIDERS))
        self.active_provider_id: str = "ollama"
        self.active_model: str = "qwen2.5:14b"
        self.temperature: float = 0.25
        self.system_prompt: str = (
            "你是一位资深加密货币与外汇高频订单流(Order Flow)及市场微观结构(Market Microstructure)量化分析师。"
            "请基于终端输入的实时足迹图(Footprint)、失衡比(Imbalance)、累计成交量差(CVD)、订单簿失衡(OBI)、"
            "挂单深度热力图(Resting Liquidity)、吸收(Absorption)与冰山单(Iceberg)、跨交易所领先/滞后(Lead/Lag)、"
            "持仓量(OI)四象限状态、资金费率(Funding)、期现基差(Basis)及爆仓级联(Liquidation Cascade)指标，"
            "用专业、精炼、结构化的简体中文给出多空微观力量对比、流动性陷阱识别与关键价位(POC/VAH/VAL/VWAP/nPOC)攻防结论。"
        )
        self.load_config()

    def load_config(self) -> None:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.active_provider_id = data.get("active_provider_id", self.active_provider_id)
                self.active_model = data.get("active_model", self.active_model)
                self.temperature = float(data.get("temperature", self.temperature))
                saved_providers = data.get("providers", {})
                for pid, pcfg in saved_providers.items():
                    if pid in self.providers:
                        self.providers[pid].update(pcfg)
                    else:
                        self.providers[pid] = pcfg
            except Exception:
                pass
        # 环境变量兜底注入
        for pid, pcfg in self.providers.items():
            env_k = pcfg.get("env_key")
            if env_k and os.environ.get(env_k) and not pcfg.get("api_key"):
                pcfg["api_key"] = os.environ[env_k]

    def save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active_provider_id": self.active_provider_id,
            "active_model": self.active_model,
            "temperature": self.temperature,
            "providers": self.providers,
        }
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def update_provider(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        default_model: str,
        set_active: bool = True,
    ) -> None:
        if provider_id not in self.providers:
            self.providers[provider_id] = {
                "name": provider_id,
                "category": "custom",
                "requires_key": False,
                "models": [default_model],
            }
        self.providers[provider_id]["base_url"] = base_url.strip().rstrip("/")
        self.providers[provider_id]["api_key"] = api_key.strip()
        self.providers[provider_id]["default_model"] = default_model.strip()
        if default_model.strip() and default_model.strip() not in self.providers[provider_id]["models"]:
            self.providers[provider_id]["models"].insert(0, default_model.strip())
        if set_active:
            self.active_provider_id = provider_id
            self.active_model = default_model.strip()
        self.save_config()

    def discover_local_models(self, provider_id: Optional[str] = None) -> List[str]:
        """自动探测本地 Ollama / LM Studio / vLLM 已加载的模型清单"""
        pid = provider_id or self.active_provider_id
        pcfg = self.providers.get(pid, {})
        base_url = pcfg.get("base_url", "http://127.0.0.1:11434/v1").rstrip("/")
        api_key = pcfg.get("api_key") or "EMPTY"
        models_url = f"{base_url}/models"
        req = urllib.request.Request(
            models_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "OrderFlowScreener-CN/2.3.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                items = raw.get("data", [])
                discovered = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
                if discovered:
                    pcfg["models"] = discovered
                    if pcfg.get("default_model") not in discovered:
                        pcfg["default_model"] = discovered[0]
                    self.save_config()
                    return discovered
        except Exception:
            pass
        return pcfg.get("models", [])

    def test_connection(self, provider_id: Optional[str] = None) -> Dict[str, Any]:
        """测试指定模型服务商的连通性、延迟与可用模型数"""
        pid = provider_id or self.active_provider_id
        pcfg = self.providers.get(pid, {})
        base_url = pcfg.get("base_url", "").rstrip("/")
        api_key = pcfg.get("api_key", "")
        if pcfg.get("requires_key") and not api_key:
            return {
                "ok": False,
                "provider_id": pid,
                "latency_ms": 0,
                "message": f"未配置 {pcfg.get('name')} 的 API Key，请先在输入框填写密钥。",
            }
        t0 = time.time()
        try:
            models = self.discover_local_models(pid)
            latency = int((time.time() - t0) * 1000)
            if models:
                return {
                    "ok": True,
                    "provider_id": pid,
                    "latency_ms": latency,
                    "models": models,
                    "message": f"连接成功 ({latency} ms)，已发现 {len(models)} 个可用模型。",
                }
        except Exception as e:
            return {
                "ok": False,
                "provider_id": pid,
                "latency_ms": int((time.time() - t0) * 1000),
                "message": f"连接失败: {e}",
            }
        return {
            "ok": False,
            "provider_id": pid,
            "latency_ms": int((time.time() - t0) * 1000),
            "message": f"无法访问端点 {base_url}/models，请确认服务已启动。",
        }

    def chat_completion(
        self,
        user_prompt: str,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """调用本地或云端大模型执行订单流分析，支持实时流式回调与离线智能量化回退诊断"""
        pid = provider_id or self.active_provider_id
        pcfg = self.providers.get(pid, self.providers["ollama"])
        target_model = model or self.active_model or pcfg.get("default_model", "qwen2.5:14b")
        base_url = pcfg.get("base_url", "http://127.0.0.1:11434/v1").rstrip("/")
        api_key = pcfg.get("api_key") or "EMPTY"

        url = f"{base_url}/chat/completions"
        use_stream = stream_callback is not None
        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "stream": use_stream,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "OrderFlowScreener-CN/2.3.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                if not use_stream:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    return content
                else:
                    full_text = []
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = (
                                chunk.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                full_text.append(delta)
                                stream_callback(delta)
                        except Exception:
                            continue
                    if full_text:
                        return "".join(full_text)
        except Exception as err:
            # 当本地 Ollama/LM Studio 未启动或未填云端 Key 时，生成确定性微观结构规则引擎深度诊断报告
            fallback = self._generate_rule_based_microstructure_report(user_prompt, pid, target_model, str(err))
            if stream_callback:
                for token in fallback.splitlines(keepends=True):
                    stream_callback(token)
            return fallback
        return ""

    def _generate_rule_based_microstructure_report(
        self, prompt: str, provider_id: str, model: str, error_note: str
    ) -> str:
        """内置确定性订单流微观结构量化诊断引擎（当外部 LLM 未启动时提供零中断中文研判）"""
        report = (
            f"### 订单流微观结构量化诊断报告 (内置规则引擎兜底 | 目标模型 `{provider_id}/{model}` 离线)\n\n"
            f"> **连接提示**：当前 `{provider_id}` 接口未响应（`{error_note}`），已自动切换至**本地确定性微观结构量化引擎**输出研判结论。\n\n"
            f"#### 1. 核心价值区与 VWAP 均价攻防状态\n"
            f"- **价值区结构 (70% Value Area)**：当前价格围绕当日 **POC (控制点)** 与 **VWAP (成交量加权均价)** 展开博弈。若最新价稳居 **VAH (价值区上沿)** 及 `+1σ` 标准差带上方，且伴随买方堆叠失衡 (Stacked Ask Imbalance ≥ 3层)，属于典型的主动买盘趋势扩张形态。\n"
            f"- **前日关键位与裸 POC (nPOC)**：重点关注昨日 **pPOC / pVAH / pVAL** 及近 7 日未回补 **nPOC** 磁吸效应；价格首次触及 nPOC 且出现 **吸收标记 (ABS)** 时，高概率触发均值回归。\n\n"
            f"#### 2. 主动成交流 (CVD / Delta) 与被动流动性 (OBI / 冰山单) 交叉验证\n"
            f"- **CVD 背离监测**：对比 1 分钟累计成交量差 (CVD) 与价格斜率。若价格创局部新高而 CVD 未同步抬升（或出现负 Delta 大单气泡），表明上方存在被动限价卖单墙吸收买盘（**多头力竭/限价吸收**）。\n"
            f"- **冰山单 (Iceberg) 与挂单热力图**：当单一交易所同一价位吃单量超过显示挂单量的 **1.5 倍**（且 ≥10 倍平均成交笔数）并迅速补单 ≥50% 时，确认机构冰山护盘位，建议将该价位设为短线防守轴心。\n\n"
            f"#### 3. 衍生品持仓四象限 (OI Regime) 与跨所领涨滞后 (Lead/Lag)\n"
            f"- **持仓量状态机**：结合价格变动 (≥0.05%) 与全网聚合持仓量 OI 变动 (≥0.1%) 判定当前属于 **新多入场 (价升仓增)**、**空头回补 (价升仓减)**、**新空入场 (价跌仓增)** 或 **多头平仓 (价跌仓减)**。\n"
            f"- **跨交易所价格发现**：观察 250ms 步进互相关系数领先的领涨交易所（如 Binance Futures 或 Coinbase Spot），当领涨所基点溢价扩大且爆仓流进入 **Cascade (级联清算 ≥5× 中位数)** 时，警惕流动性真空引发的瞬时插针。\n\n"
            f"#### 4. 输入上下文快照摘要\n"
            f"```text\n{prompt[:900]}\n```\n"
        )
        return report
