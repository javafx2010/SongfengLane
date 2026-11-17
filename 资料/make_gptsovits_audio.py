# -*- coding: utf-8 -*-
"""GPT-SoVITS 分角色配音合成脚本（api_v2，可复用于全书各章）。

用法：python 资料/make_gptsovits_audio.py 资料/配音稿_第001章.txt
依赖：GPT-SoVITS api_v2 服务已启动（127.0.0.1:9880，--no-auto-load 时可热切权重）、ffmpeg。
输入：配音标注稿（每段一行，行首 [角色代码]，代码见 ROLE2VOICE）。
输出：音频/卷一/第NNN章_章名.mp3 + 同名 .lrc（按脚本原顺序拼接）。
特性：按角色分组请求（同一角色只切换一次模型权重）；断点续跑（分段缓存）。
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
import concurrent.futures as cf

API = "http://127.0.0.1:9880"
STAGE = Path(r"F:\GPT-SoVITS\_tts_stage")
GAP_SEC = 0.45
BASE = Path(__file__).resolve().parent.parent
TITLE_MAP = {"第001章": "第001章_一九九八年的夏天"}

# 角色 → (模型目录, speed_factor)。音色均取自 _tts_stage 已训练模型与 ref.wav。
ROLE2VOICE = {
    "N": ("n07_shenhe",     1.00),  # 旁白（女声）
    "S": ("n12_nahida",     1.05),  # 苏冬梅（六岁）
    "M": ("n11_xianyun",    1.00),  # 母亲周惠兰
    "F": ("n10_baishu",     1.00),  # 父亲苏德海
    "P": ("n06_hutao",      1.05),  # 胖丫
    "Q": ("n05_ningguang",  1.00),  # 琴课老师
    "O": ("n09_zhongli",    0.97),  # 老校长/老头/远房/师傅
    "W": ("m03_sanyueqi",   1.00),  # 女群杂
    "K": ("m08_walter",     0.95),  # 单位客人
}


def load_meta(alias: str):
    meta = json.loads((STAGE / alias / "meta.json").read_text(encoding="utf-8")) \
        if (STAGE / alias / "meta.json").exists() else None
    ref = STAGE / alias / "ref.wav"
    if not ref.exists():
        raise FileNotFoundError(ref)
    if meta and meta.get("prompt_text"):
        prompt = meta["prompt_text"]
    else:
        # 从 _tts_stage/voices.json 兜底取 prompt_text
        for v in json.loads((STAGE / "voices.json").read_text(encoding="utf-8")):
            if v.get("alias") == alias:
                prompt = v["prompt_text"]
                break
        else:
            prompt = ref.stem
    return str(ref), prompt


def parse_script(path: Path):
    segs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith("["):
            continue
        code, _, text = line.partition("]")
        code = code.strip("[]")
        if code not in ROLE2VOICE:
            raise ValueError(f"未知角色代码：{code}")
        if text.strip():
            segs.append((code, text.strip()))
    return segs


def set_weights(alias: str) -> None:
    gpt = str(STAGE / alias / "gpt.ckpt")
    sovits = str(STAGE / alias / "sovits.pth")
    for kind, w in (("set_gpt_weights", gpt), ("set_sovits_weights", sovits)):
        r = requests.get(f"{API}/{kind}", params={"weights_path": w}, timeout=180)
        r.raise_for_status()


def synth(text: str, ref: str, prompt: str, speed: float) -> bytes:
    payload = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref,
        "prompt_text": prompt,
        "prompt_lang": "zh",
        "text_split_method": "cut5",
        "batch_size": 10,
        "speed_factor": speed,
        "media_type": "wav",
        "streaming_mode": False,
    }
    last = None
    for attempt in range(4):
        try:
            r = requests.post(f"{API}/tts", json=payload, timeout=600)
            if r.ok and len(r.content) > 2000:
                return r.content
            last = RuntimeError(f"API {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            last = e
        time.sleep(3 * (attempt + 1))
    raise last


def probe(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(p.stdout.strip())


def main(script_path: Path, out_path: Path) -> None:
    segs = parse_script(script_path)
    total_chars = sum(len(t) for _, t in segs)
    print(f"共 {len(segs)} 段 / {total_chars} 字")

    work = out_path.parent / f"_gsv_{out_path.stem}"
    work.mkdir(parents=True, exist_ok=True)

    # 按角色分组（保持首次出现顺序），同角色只切一次权重
    order, groups = [], {}
    for i, (code, text) in enumerate(segs):
        if code not in groups:
            groups[code] = []
            order.append(code)
        groups[code].append((i, text))

    for code in order:
        alias, speed = ROLE2VOICE[code]
        todo = [(i, t) for i, t in groups[code]
                if not (work / f"{i:04d}.wav").exists()]
        if todo:
            print(f"[{code}] {alias}：{len(todo)} 段待合成，切换权重…")
            set_weights(alias)
            ref, prompt = load_meta(alias)
            with cf.ThreadPoolExecutor(max_workers=2) as ex:
                futs = {ex.submit(synth, t, ref, prompt, speed): i for i, t in todo}
                for n, f in enumerate(cf.as_completed(futs), 1):
                    data = f.result()
                    (work / f"{futs[f]:04d}.wav").write_bytes(data)
                    if n % 10 == 0:
                        print(f"  [{code}] {n}/{len(todo)}", flush=True)
        if not todo:
            print(f"[{code}] {alias}：已缓存，跳过")

    print("拼接音频…")
    durs = [probe(work / f"{i:04d}.wav") for i in range(len(segs))]
    list_file = work / "list.txt"
    list_file.write_text(
        "\n".join(f"file '{(work / f'{i:04d}.wav').as_posix()}'" for i in range(len(segs))),
        encoding="utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(list_file),
                    "-c:a", "libmp3lame", "-q:a", "4", str(out_path)], check=True)

    def fmt(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    lrc_lines = [f"[{fmt(0.0)}]《松风巷的女儿》· {out_path.stem}"]
    cursor = 0.0
    for (code, text), d in zip(segs, durs):
        cursor += d + GAP_SEC
        lrc_lines.append(f"[{fmt(cursor)}]{text}")
    out_path.with_suffix(".lrc").write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")

    secs = probe(out_path)
    print(f"完成 → {out_path}（{int(secs // 60)}分{int(secs % 60):02d}秒，分段缓存保留在 {work}）")


if __name__ == "__main__":
    script = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "资料" / "配音稿_第001章.txt"
    stem = script.stem.replace("配音稿_", "")
    ch = stem.split("_")[0] if "_" in stem else stem
    name = TITLE_MAP.get(ch, ch)
    out = BASE / "音频" / "卷一" / f"{name}.mp3"
    main(script, out)
