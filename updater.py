#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用内自动更新与上游同步检查模块 (updater.py)
支持：
1. 检查用户 Fork 仓库 (gouqizi2214730-source/order-flow-screener) 最新 GitHub Release 中的
   `OrderFlowScreener-Setup-win64.exe` 安装包版本。
2. 检查上游源仓库 (zadescoxp/order-flow-screener) 最新 Release 与 Commit 动态。
3. 在 Windows 环境下自动下载最新 `OrderFlowScreener-Setup-win64.exe` 并通过 `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`
   无黑框 (`CREATE_NO_WINDOW`) 执行一键静默覆盖升级。
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, Callable


APP_VERSION = "v2.3.0"
FORK_REPO = "gouqizi2214730-source/order-flow-screener"
UPSTREAM_REPO = "zadescoxp/order-flow-screener"
INSTALLER_ASSET_NAME = "OrderFlowScreener-Setup-win64.exe"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class AutoUpdater:
    """管理 GitHub Releases 自动检查、上游版本对比与 Windows 静默安装器升级"""

    def __init__(
        self,
        current_version: str = APP_VERSION,
        fork_repo: str = FORK_REPO,
        upstream_repo: str = UPSTREAM_REPO,
    ):
        self.current_version = current_version
        self.fork_repo = fork_repo
        self.upstream_repo = upstream_repo

    @staticmethod
    def _normalize_ver(tag: str) -> tuple:
        clean = tag.strip().lstrip("vV").split("-")[0]
        parts = []
        for p in clean.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def check_for_updates(self) -> Dict[str, Any]:
        """同时检查用户 Fork 仓库的中文安装包 Release 与上游源项目 Release"""
        result: Dict[str, Any] = {
            "current_version": self.current_version,
            "fork_repo": self.fork_repo,
            "upstream_repo": self.upstream_repo,
            "latest_fork_tag": self.current_version,
            "latest_upstream_tag": "v2.3.0",
            "has_update": False,
            "download_url": "",
            "release_notes": "",
            "published_at": "",
            "status_message": "",
        }

        # 1. 查询 Fork 仓库 Releases
        fork_api = f"https://api.github.com/repos/{self.fork_repo}/releases/latest"
        try:
            req = urllib.request.Request(
                fork_api,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "OrderFlowScreener-CN-Updater/2.3.0",
                },
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tag = data.get("tag_name", self.current_version)
                result["latest_fork_tag"] = tag
                result["release_notes"] = data.get("body", "")
                result["published_at"] = data.get("published_at", "")
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith("-Setup-win64.exe") or name == INSTALLER_ASSET_NAME:
                        result["download_url"] = asset.get("browser_download_url", "")
                        break
                if self._normalize_ver(tag) > self._normalize_ver(self.current_version):
                    result["has_update"] = True
        except Exception:
            pass

        # 2. 查询上游 zadescoxp/order-flow-screener 最新 Release
        upstream_api = f"https://api.github.com/repos/{self.upstream_repo}/releases/latest"
        try:
            req_up = urllib.request.Request(
                upstream_api,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "OrderFlowScreener-CN-Updater/2.3.0",
                },
            )
            with urllib.request.urlopen(req_up, timeout=5.0) as resp:
                up_data = json.loads(resp.read().decode("utf-8"))
                result["latest_upstream_tag"] = up_data.get("tag_name", "v2.3.0")
        except Exception:
            pass

        if result["has_update"]:
            result["status_message"] = (
                f"发现新版本 {result['latest_fork_tag']} (当前 {self.current_version})，可一键下载并静默升级！"
            )
        else:
            result["status_message"] = (
                f"当前已是最新中文桌面版 ({self.current_version}) | 上游基准版本: {result['latest_upstream_tag']}"
            )
        return result

    def download_and_install_update(
        self,
        download_url: str,
        silent: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """下载最新 OrderFlowScreener-Setup-win64.exe 并启动 Inno Setup 静默安装器"""
        if not download_url:
            download_url = f"https://github.com/{self.fork_repo}/releases/latest/download/{INSTALLER_ASSET_NAME}"

        target_dir = Path(tempfile.gettempdir()) / "OrderFlowScreenerUpdate"
        target_dir.mkdir(parents=True, exist_ok=True)
        installer_path = target_dir / INSTALLER_ASSET_NAME

        try:
            if progress_callback:
                progress_callback(10, f"正在连接 GitHub Release 下载 {INSTALLER_ASSET_NAME} ...")
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "OrderFlowScreener-CN-Updater/2.3.0"},
            )
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                total = int(resp.headers.get("Content-Length", "0"))
                downloaded = 0
                with installer_path.open("wb") as out_f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_callback:
                            pct = min(90, 10 + int(downloaded * 80 / total))
                            progress_callback(pct, f"已下载 {downloaded // 1024} KB / {total // 1024} KB")

            if sys.platform == "win32":
                args = [str(installer_path)]
                if silent:
                    args.extend(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"])
                if progress_callback:
                    progress_callback(95, "正在启动 Inno Setup 静默覆盖安装...")
                subprocess.Popen(args, creationflags=CREATE_NO_WINDOW)
                return {
                    "ok": True,
                    "installer_path": str(installer_path),
                    "message": "已启动安装程序，应用即将自动完成平滑更新。",
                }
            else:
                return {
                    "ok": True,
                    "installer_path": str(installer_path),
                    "message": f"安装包已下载至 {installer_path}（当前为非 Windows 沙盒环境，未执行 Win32 安装命令）。",
                }
        except Exception as e:
            return {
                "ok": False,
                "installer_path": str(installer_path),
                "message": f"自动下载或启动安装器失败: {e}",
            }
