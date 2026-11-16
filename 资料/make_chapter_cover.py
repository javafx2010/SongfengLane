# -*- coding: utf-8 -*-
"""章节封面出图脚本（复用整书封面工作流，按章替换提示词）。

用法：python 资料/make_chapter_cover.py 第001章 4
依赖：make_cover.py（同一目录）、ComfyUI 运行于 127.0.0.1:8188。
输出：封面/章节/<章名>/cover_*.png
"""
import asyncio
import random
import sys
from pathlib import Path

import make_cover as mc

# 各章场景提示词（画风锁定：meinamix 暖巷插画风，2026-11-16 用户定稿）
CHAPTER_PROMPTS = {
    "第001章": (
        "masterpiece, best quality, vertical illustration, "
        "chinese old narrow alley in early morning, soft golden dawn light, "
        "wet flagstone path, weathered grey brick wall with laundry lines, "
        "an old wooden piano stool leaning against the wall near an open door, "
        "back view of a young chinese girl 18 years old, black ponytail, "
        "(plain white dress:1.3), holding a vintage leather suitcase, "
        "pausing at the alley entrance, looking back over her shoulder, "
        "long morning shadow, floating dust in the light beam, "
        "nostalgic 1990s small town, warm melancholic mood, highly detailed"
    ),
}
CHAPTER_NEG = (
    "text, watermark, signature, logo, title, lowres, blurry, jpeg artifacts, "
    "deformed hands, extra limbs, bad anatomy, oversaturated, worst quality, "
    "black dress, dark dress"
)


async def run(chapter: str, count: int) -> None:
    if chapter not in CHAPTER_PROMPTS:
        raise SystemExit(f"未配置该章提示词：{chapter}（请在 CHAPTER_PROMPTS 添加）")

    mc.POSITIVE = CHAPTER_PROMPTS[chapter]
    mc.NEGATIVE = CHAPTER_NEG

    out_dir = mc.BASE if hasattr(mc, "BASE") else Path(__file__).resolve().parent.parent
    out_dir = Path(out_dir) / "封面" / "章节" / chapter
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(1, count + 1):
        seed = random.randint(1, 10**9)
        print(f"[{idx}/{count}] seed={seed} 提交中…")
        pid = mc.post_prompt(mc.build_workflow("meinamix_v10.safetensors", seed, cfg=7.0))
        print(f"  prompt_id={pid} 等待生成…")
        for img in mc.wait_result(pid):
            dest = out_dir / f"cover_{chapter}_seed{seed}_{img['filename'].split('_')[-1]}"
            mc.download(img, dest)
            print(f"  已保存 → {dest}")
    print("完成。")


if __name__ == "__main__":
    ch = sys.argv[1] if len(sys.argv) > 1 else "第001章"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    asyncio.run(run(ch, n))
