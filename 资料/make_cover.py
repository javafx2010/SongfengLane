# -*- coding: utf-8 -*-
"""《松风巷的女儿》封面生成脚本（走本机 ComfyUI API，可重复运行）。

用法：python 资料/make_cover.py [数量]
依赖：仅标准库（urllib），无需额外安装。
输出：封面/cover_001_*.png 等。
"""
import json
import random
import sys
import urllib.error
import urllib.request
import urllib.parse
import uuid
from pathlib import Path

HOST = "http://127.0.0.1:8188"
OUT_DIR = Path(__file__).resolve().parent.parent / "封面"

POSITIVE = (
    "masterpiece, best quality, vertical book cover composition, "
    "nostalgic southern chinese old alley at dusk, narrow lane with worn flagstone path, "
    "dim yellow street lamp, weathered grey brick wall with laundry lines, "
    "an old wooden piano stool leaning against the wall near the door, "
    "back view of an elegant 18-year-old chinese girl, black ponytail, "
    "(plain white dress:1.4), holding a vintage leather suitcase, "
    "walking away from camera, long shadow, "
    "melancholic warm cinematic lighting, floating dust in the light beam, "
    "1990s small town atmosphere, highly detailed"
)
NEGATIVE = (
    "text, watermark, signature, logo, title, lowres, blurry, jpeg artifacts, "
    "deformed hands, extra limbs, bad anatomy, oversaturated, cartoon, worst quality, "
    "black dress, dark dress"
)


def build_workflow(checkpoint: str, seed: int, width=832, height=1216,
                   steps=30, cfg=5.5) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": POSITIVE, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "dpmpp_2m", "scheduler": "karras",
                         "denoise": 1.0,
                         "model": ["1", 0], "positive": ["2", 0],
                         "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "songfeng", "images": ["6", 0]}},
    }


def post_prompt(workflow: dict) -> str:
    body = json.dumps({"prompt": workflow,
                       "client_id": str(uuid.uuid4())}).encode("utf-8")
    req = urllib.request.Request(HOST + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["prompt_id"]
    except urllib.error.HTTPError as e:
        print("服务端拒绝：", e.read().decode("utf-8", "replace"))
        raise


def wait_result(prompt_id: str, timeout=600) -> list:
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(f"{HOST}/history/{prompt_id}", timeout=30) as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            outputs = hist[prompt_id].get("outputs", {})
            imgs = [i for node in outputs.values()
                    for i in node.get("images", [])]
            if imgs:
                return imgs
        time.sleep(3)
    raise TimeoutError("生成超时")


def download(img: dict, save_path: Path) -> None:
    q = urllib.parse.urlencode({k: img[k] for k in
                                ("filename", "subfolder", "type")})
    with urllib.request.urlopen(f"{HOST}/view?{q}", timeout=60) as r:
        save_path.write_bytes(r.read())


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    # 封面画风已定稿：meinamix 暗调夜巷插画（用户 2026-11-16 选定）
    plans = [("meinamix_v10.safetensors", random.randint(1, 10**9), "插画")
             for _ in range(count)]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for idx, (ckpt, seed, tag) in enumerate(plans, 1):
        print(f"[{idx}/{len(plans)}] {tag} ckpt={ckpt} seed={seed} 提交中…")
        pid = post_prompt(build_workflow(ckpt, seed,
                                         cfg=5.5 if tag == "写实" else 7.0))
        print(f"  prompt_id={pid} 等待生成…")
        for img in wait_result(pid):
            name = f"cover_001_{tag}_seed{seed}_{img['filename'].split('_')[-1]}"
            dest = OUT_DIR / name
            download(img, dest)
            print(f"  已保存 → {dest}")
    print("完成。")


if __name__ == "__main__":
    main()
