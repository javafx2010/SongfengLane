# -*- coding: utf-8 -*-
"""Google Cloud TTS 分角色配音合成脚本（可复用于全书各章）。

用法：python 资料/make_google_tts_audio.py 资料/配音稿_第001章.txt
依赖：google-cloud-texttospeech（REST 直连，仅需凭据文件）、requests、ffmpeg（PATH）。
网络：需经本地代理访问 Google 端点（PROXY），凭据见 KEY_PATH。
输入：配音标注稿（每段一行，行首 [角色代码]，代码见 VOICES）。
输出：音频/卷一/第NNN章_章名.mp3 + 同名 .lrc
"""
import base64
import asyncio
import concurrent.futures as cf
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
import edge_tts
from google.oauth2 import service_account
from google.auth.transport.requests import Request as AuthRequest

KEY_PATH = r"C:\Users\Admin\.config\gcp\tts-key.json"
PROXY = "http://127.0.0.1:7890"
API = "https://texttospeech.googleapis.com/v1/text:synthesize"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# Edge-TTS 角色 → (音色, rate, pitch)。N 旁白小艺（少女），S 苏冬梅晓晓（童声感升调）。
EDGE = {
    "N": ("zh-CN-XiaoyiNeural",  "-5%", None),
    "S": ("zh-CN-XiaoxiaoNeural", "+8%", "+20Hz"),
}
# 其余角色 → Google cmn-CN Wavenet/Standard（name, rate, pitch）。
VOICES = {
    "M": ("cmn-CN-Wavenet-C",   0.92,  -2),  # 母亲周惠兰
    "F": ("cmn-CN-Wavenet-B",   0.92,  -2),  # 父亲苏德海
    "P": ("cmn-CN-Standard-A",  1.00,  10),  # 胖丫
    "Q": ("cmn-CN-Standard-C",  0.95,   0),  # 琴课老师
    "O": ("cmn-CN-Standard-D",  0.88,  -6),  # 老校长/老头/远房/师傅
    "W": ("cmn-CN-Wavenet-A",   1.00,   0),  # 女群杂
    "K": ("cmn-CN-Standard-B",  0.90,  -4),  # 单位客人
}

GAP_SEC = 0.45
BASE = Path(__file__).resolve().parent.parent
TITLE_MAP = {"第001章": "第001章_一九九八年的夏天"}


def get_credentials():
    creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    creds.refresh(AuthRequest())
    return creds


def parse_script(path: Path):
    segs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith("["):
            continue
        code, _, text = line.partition("]")
        code = code.strip("[]")
        if code not in EDGE and code not in VOICES:
            raise ValueError(f"未知角色代码：{code}")
        if text.strip():
            segs.append((code, text.strip()))
    return segs


EDGE_SEM = threading.BoundedSemaphore(2)


async def _edge_once(text: str, voice: str, rate: str, pitch) -> bytes:
    kw = {"rate": rate}
    if pitch:
        kw["pitch"] = pitch
    com = edge_tts.Communicate(text, voice, **kw)
    buf = b""
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf += chunk["data"]
    if len(buf) < 1000:
        raise RuntimeError("edge-tts 返回空音频")
    return buf


def synth_edge(text: str, voice: str, rate: str, pitch) -> bytes:
    with EDGE_SEM:
        for attempt in range(6):
            try:
                return asyncio.run(_edge_once(text, voice, rate, pitch))
            except Exception as e:
                if attempt == 5:
                    raise
                time.sleep(3 + 3 * attempt)


def synth_one(session, token, code, text) -> bytes:
    if code in EDGE:
        v, r, p = EDGE[code]
        return synth_edge(text, v, r, p)
    voice, rate, pitch = VOICES[code]
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "cmn-CN", "name": voice},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate, "pitch": pitch},
    }
    for attempt in range(4):
        try:
            r = session.post(
                API, json=body,
                headers={"Authorization": f"Bearer {token}"},
                proxies={"https": PROXY, "http": PROXY},
                timeout=90,
            )
            if r.ok:
                return base64.b64decode(r.json()["audioContent"])
            if r.status_code in (429, 500, 503):
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"TTS API {r.status_code}: {r.text[:200]}")
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("合成失败")


def main(script_path: Path, out_path: Path) -> None:
    segs = parse_script(script_path)
    total_chars = sum(len(t) for _, t in segs)
    print(f"共 {len(segs)} 段 / {total_chars} 字，开始合成…")

    creds = get_credentials()
    session = requests.Session()
    work = out_path.parent / f"_gparts_{out_path.stem}"
    work.mkdir(parents=True, exist_ok=True)

    def job(i, code, text):
        cached = work / f"{i:04d}.mp3"
        if cached.exists() and cached.stat().st_size > 1000:
            return i
        data = synth_one(session, creds.token, code, text)
        cached.write_bytes(data)
        return i

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(job, i, c, t) for i, (c, t) in enumerate(segs)]
        for k, f in enumerate(cf.as_completed(futs), 1):
            f.result()
            if k % 20 == 0:
                print(f"  已完成 {k}/{len(segs)}")

    print("分段语音完成，探测时长…")
    durs = []
    for i in range(len(segs)):
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(work / f"{i:04d}.mp3")],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        durs.append(float(p.stdout.strip()))

    gap = work / "gap.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(GAP_SEC), "-q:a", "9", str(gap)], check=True)

    list_file = work / "list.txt"
    lines = []
    for i in range(len(segs)):
        lines.append(f"file '{(work / f'{i:04d}.mp3').as_posix()}'")
        lines.append(f"file '{gap.as_posix()}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

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

    shutil.rmtree(work, ignore_errors=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = float(probe.stdout.strip() or 0)
    print(f"完成 → {out_path}（{int(secs // 60)}分{int(secs % 60):02d}秒）")


if __name__ == "__main__":
    script = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "资料" / "配音稿_第001章.txt"
    stem = script.stem.replace("配音稿_", "")
    ch = stem.split("_")[0] if "_" in stem else stem
    name = TITLE_MAP.get(ch, ch)
    out = BASE / "音频" / "卷一" / f"{name}.mp3"
    main(script, out)
