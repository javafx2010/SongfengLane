# -*- coding: utf-8 -*-
"""基于已有封面图做 img2img（保留构图，改人物/细节）。

用法：python 资料/make_cover_img2img.py <源图路径> <正向提示词> <输出文件名> [denoise]
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HOST = "http://127.0.0.1:8188"
CKPT = "animagine-xl-4.0-opt.safetensors"
BASE = Path(__file__).resolve().parent.parent

NEG = (
    "lowres, bad anatomy, bad hands, text, watermark, signature, username, "
    "worst quality, low quality, jpeg artifacts, blurry, deformed, extra limbs, "
    "realistic, photo, photorealistic, 3d render"
)


def upload(path: Path) -> str:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        f"{HOST}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["name"]


def post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def main(src: Path, pos: str, name: str, denoise: float) -> None:
    img_name = upload(src)
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "10": {"class_type": "LoadImage", "inputs": {"image": img_name}},
        "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": 20261117, "steps": 30, "cfg": 4.5,
            "sampler_name": "euler_ancestral", "scheduler": "normal",
            "denoise": denoise, "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["11", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "cover_i2i", "images": ["8", 0]}},
    }
    pid = post(f"{HOST}/prompt", {"prompt": wf, "client_id": "songfeng-i2i"})["prompt_id"]
    print("prompt_id:", pid)
    while pid not in json.loads(urllib.request.urlopen(f"{HOST}/history/{pid}", timeout=60).read()):
        time.sleep(2)
    hist = json.loads(urllib.request.urlopen(f"{HOST}/history/{pid}", timeout=60).read())[pid]
    img = hist["outputs"]["9"]["images"][0]
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
    data = urllib.request.urlopen(f"{HOST}/view?{q}", timeout=120).read()
    out = BASE / "封面" / f"{name}.png"
    out.write_bytes(data)
    print("saved:", out, f"({len(data) // 1024} KB)")


if __name__ == "__main__":
    src = Path(sys.argv[1])
    main(src, sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.62)
