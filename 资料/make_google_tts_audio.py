# -*- coding: utf-8 -*-
"""分角色配音合成脚本（旁白/苏冬梅=Edge-TTS，其余=Google Chirp 3 HD）。可复用于全书各章。

用法：
  python 资料/make_google_tts_audio.py 资料/配音稿_第001章.txt          # 全章合成
  python 资料/make_google_tts_audio.py --probe                          # 仅探测各 Chirp 3 音色可用性
依赖：google-cloud-texttospeech 凭据、requests、edge-tts、ffmpeg（PATH）。
网络：Google 端点需经本地代理（PROXY），凭据见 KEY_PATH。
输入：配音标注稿（每段一行，行首 [角色代码]，代码见 EDGE/VOICES）。
输出：章节/卷X_卷名/第NNN章_章名/第NNN章_章名.mp3
"""
import base64
import asyncio
import concurrent.futures as cf
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

# Edge-TTS 角色 → (音色, rate, pitch)。N 旁白小艺，S 苏冬梅晓晓（童声感升调）。语速一律默认。
EDGE = {
    "N": ("zh-CN-XiaoyiNeural",   None, None),
    "S": ("zh-CN-XiaoxiaoNeural", None, "+20Hz"),
}
# 其余角色 → Google Chirp 3 HD（cmn-CN-Chirp3-HD-*，name, rate）。语速一律 1.0，不做快慢处理。
# 注：Chirp 3 不保证支持 pitch；rate 由 audioConfig.speakingRate 控制，
# 若服务端报 400 则自动降级为不带 audioConfig 重试。
VOICES = {
    "M": ("cmn-CN-Chirp3-HD-Gacrux",  1.00),  # 母亲周惠兰（女，偏年长）
    "F": ("cmn-CN-Chirp3-HD-Charon",  1.00),  # 父亲苏德海（男，沉稳）
    "P": ("cmn-CN-Chirp3-HD-Kore",    1.00),  # 胖丫（女，明快）
    "Q": ("cmn-CN-Chirp3-HD-Zephyr",  1.00),  # 琴课老师（女，清亮）
    "O": ("cmn-CN-Chirp3-HD-Iapetus", 1.00),  # 老校长/老关头/老张头/白医生（男，偏老）
    "W": ("cmn-CN-Chirp3-HD-Leda",    1.00),  # 女群杂
    "K": ("cmn-CN-Chirp3-HD-Orus",    1.00),  # 单位客人（男，中年）
}

GAP_SEC = 0.45
BASE = Path(__file__).resolve().parent.parent
PROBE_TEXT = "今天是个好日子。"


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


async def _edge_once(text: str, voice: str, rate, pitch) -> bytes:
    kw = {}
    if rate:
        kw["rate"] = rate
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
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(3 + 3 * attempt)


def _post(session, token, body):
    return session.post(
        API, json=body,
        headers={"Authorization": f"Bearer {token}"},
        proxies={"https": PROXY, "http": PROXY},
        timeout=90,
    )


def synth_google(session, token, text, voice_name, rate):
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "cmn-CN", "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate},
    }
    for attempt in range(5):
        try:
            r = _post(session, token, body)
            if r.ok:
                return base64.b64decode(r.json()["audioContent"])
            if r.status_code == 400 and "audioConfig" in body:
                # Chirp 3 可能不接受 speakingRate → 降级重试
                body = {"input": body["input"], "voice": body["voice"]}
                continue
            if r.status_code in (429, 500, 503):
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"TTS API {r.status_code}: {r.text[:300]}")
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("合成失败")


def synth_one(session, token, code, text) -> bytes:
    if code in EDGE:
        v, r, p = EDGE[code]
        return synth_edge(text, v, r, p)
    voice, rate = VOICES[code]
    return synth_google(session, token, text, voice, rate)


def probe():
    """逐个探测 Chirp 3 音色可用性。"""
    creds = get_credentials()
    session = requests.Session()
    for code, (voice, rate) in VOICES.items():
        try:
            data = synth_google(session, creds.token, PROBE_TEXT, voice, rate)
            print(f"[OK] {code} {voice}  ({len(data)} bytes, rate={rate})")
        except Exception as e:
            print(f"[FAIL] {code} {voice}  {e}")


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

    print("分段语音完成，拼接…")
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

    shutil.rmtree(work, ignore_errors=True)
    probe_out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = float(probe_out.stdout.strip() or 0)
    print(f"完成 → {out_path}（{int(secs // 60)}分{int(secs % 60):02d}秒）")


def find_chapter_dir(ch: str) -> Path:
    """章节/卷X_卷名/第NNN章_章名/ 中定位章节目录。"""
    hits = sorted((BASE / "章节").glob(f"*/{ch}_*"))
    if not hits:
        raise FileNotFoundError(f"章节目录不存在：章节/*/ {ch}_*")
    return hits[0]


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
        sys.exit(0)
    script = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "资料" / "配音稿_第001章.txt"
    stem = script.stem.replace("配音稿_", "")
    ch = stem.split("_")[0] if "_" in stem else stem
    chdir = find_chapter_dir(ch)
    out = chdir / f"{chdir.name}.mp3"
    main(script, out)
