#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 Order Flow Screener (订单流微观结构终端) 256px 多尺寸高清 Windows 图标 (.ico)
支持 256x256, 128x128, 64x64, 48x48, 32x32, 16x16 多级分辨率，确保 Windows 桌面与任务栏清晰无模糊。
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate_app_icon(output_path: str = "app_icon_v230.ico") -> str:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 绘制现代圆角深色渐变感底板 (#0B1020 -> #131C31)
    margin = 12
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=48,
        fill=(13, 19, 34, 255),
        outline=(45, 212, 191, 220),
        width=6,
    )

    # 2. 绘制内部热力网格线
    for y in range(56, 205, 36):
        draw.line([(36, y), (size - 36, y)], fill=(30, 41, 59, 180), width=2)

    # 3. 绘制左侧卖方流动性深度阶梯 (珊瑚红 #F43F5E) 与右侧买方流动性阶梯 (翠绿 #10B981)
    # 模拟足迹图 Footprint Bid x Ask 阶梯与 POC 黄金框
    bars = [
        (60, 48, 68, False),
        (92, 82, 54, False),
        (124, 96, 104, True),   # POC 核心成交密集区
        (156, 62, 88, False),
        (188, 44, 72, False),
    ]
    center_x = size // 2
    for y_top, bid_w, ask_w, is_poc in bars:
        bar_h = 22
        # 左侧 Bid (卖方主动成交流, 红/橙色)
        draw.rounded_rectangle(
            [center_x - 6 - bid_w, y_top, center_x - 6, y_top + bar_h],
            radius=5,
            fill=(244, 63, 94, 235),
        )
        # 右侧 Ask (买方主动成交流, 青绿色)
        draw.rounded_rectangle(
            [center_x + 6, y_top, center_x + 6 + ask_w, y_top + bar_h],
            radius=5,
            fill=(16, 185, 129, 235),
        )
        if is_poc:
            # POC 亮金色高亮外框
            draw.rounded_rectangle(
                [center_x - 10 - bid_w, y_top - 4, center_x + 10 + ask_w, y_top + bar_h + 4],
                radius=7,
                outline=(250, 204, 21, 255),
                width=3,
            )

    # 4. 绘制中心 VWAP 均价折线与大单气泡 (Big Print Bubble)
    vwap_points = [(64, 196), (104, 160), (132, 134), (168, 96), (202, 68)]
    draw.line(vwap_points, fill=(56, 189, 248, 255), width=5)

    # 大单爆仓气泡
    bx, by, br = 168, 96, 16
    draw.ellipse(
        [bx - br, by - br, bx + br, by + br],
        fill=(250, 204, 21, 220),
        outline=(255, 255, 255, 255),
        width=3,
    )

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(str(out_file), format="ICO", sizes=icon_sizes)
    png_preview = out_file.with_suffix(".png")
    img.save(str(png_preview), format="PNG")
    return str(out_file)


if __name__ == "__main__":
    target = os.environ.get("ICON_OUTPUT", "app_icon_v230.ico")
    saved = generate_app_icon(target)
    print(f"Generated multi-size 256px icon at: {saved}")
