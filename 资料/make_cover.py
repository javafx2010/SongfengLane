# -*- coding: utf-8 -*-
"""通过 ComfyUI API（127.0.0.1:8188，RealVisXL V5.0）生成章节封面。

用法：python 资料/make_cover.py "正向提示词" [输出文件名]
输出：封面/<输出文件名>.png
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "http://127.0.0.1:8188"
CKPT = "animagine-xl-4.0-opt.safetensors"
OUT_DIR = Path(__file__).resolve().parent.parent / "封面"

POS = sys.argv[1] if len(sys.argv) > 1 else ""
NEG = (
    "lowres, bad anatomy, bad hands, text, watermark, signature, username, "
    "worst quality, low quality, jpeg artifacts, blurry, deformed, extra limbs, "
    "realistic, photo, photorealistic, 3d render"
)

wf = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["4", 1]}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": 1216, "batch_size": 1}},
    "3": {"class_type": "KSampler", "inputs": {
        "seed": 20261117, "steps": 28, "cfg": 4.5,
        "sampler_name": "euler_ancestral", "scheduler": "normal",
        "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
        "negative": ["7", 0], "latent_image": ["5", 0]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "cover", "images": ["8", 0]}},
}


def post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


import time

r = post(f"{HOST}/prompt", {"prompt": wf, "client_id": "songfeng-cover"})
pid = r["prompt_id"]
print("prompt_id:", pid)

while pid not in json.loads(urllib.request.urlopen(f"{HOST}/history/{pid}", timeout=60).read()):
    time.sleep(2)

hist = json.loads(urllib.request.urlopen(f"{HOST}/history/{pid}", timeout=60).read())[pid]
outs = hist["outputs"]["9"]["images"]
img = outs[0]
q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
data = urllib.request.urlopen(f"{HOST}/view?{q}", timeout=120).read()

OUT_DIR.mkdir(parents=True, exist_ok=True)
name = sys.argv[2] if len(sys.argv) > 2 else img["filename"].rsplit("_", 1)[0]

import re
m = re.match(r"第(\d{3})章", name)
if m:
    hits = sorted((OUT_DIR.parent / "章节").glob(f"*/第{m.group(1)}章_*"))
    if hits:
        out_dir = hits[0] / "封面"
        out_dir.mkdir(parents=True, exist_ok=True)
        OUT_DIR = out_dir

out = OUT_DIR / f"{name}.png"
out.write_bytes(data)
print("saved:", out, f"({len(data) // 1024} KB)")
