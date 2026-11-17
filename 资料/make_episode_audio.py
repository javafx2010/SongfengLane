# -*- coding: utf-8 -*-
"""edge-tts 分角色配音合成脚本（可复用于全书各章）。

用法：python 资料/make_episode_audio.py 资料/配音稿_第006章.txt
依赖：edge-tts（已装入 F:\\ComfyUI\\venv）、ffmpeg（PATH）。
输入：配音标注稿（每段一行，行首 [角色代码]，代码见 VOICES）。
输出：音频/卷一/第006章_十八岁的巷口.mp3
"""
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts

# 角色 → 音色/语速/音高（2026-11-17 首次用于第006章）
VOICES = {
    "N": ("zh-CN-XiaoxiaoNeural", "-8%",  "+0Hz"),   # 旁白
    "S": ("zh-CN-XiaoyiNeural",   "-12%", "+0Hz"),   # 苏冬梅
    "M": ("zh-CN-XiaoxiaoNeural", "-30%", "+0Hz"),   # 母亲周惠兰
    "W": ("zh-CN-XiaoxiaoNeural", "+8%",  "+5Hz"),   # 王婶
    "X": ("zh-CN-XiaoxiaoNeural", "-18%", "+15Hz"),  # 孙婶
    "L": ("zh-CN-XiaoxiaoNeural", "-25%", "+18Hz"),  # 六婆
    "D": ("zh-CN-YunxiaNeural",   "+0%",  "+0Hz"),   # 弟弟
    "Y": ("zh-CN-YunjianNeural",  "+0%",  "+0Hz"),   # 邮递员
    "F": ("zh-CN-XiaoxiaoNeural", "+12%", "+10Hz"),  # 女群杂
    "O": ("zh-CN-YunjianNeural",  "+3%",  "+0Hz"),   # 男群杂（老韩等）
    "T": ("zh-CN-XiaoxiaoNeural", "-10%", "+0Hz"),   # 吴老师
    "J": ("zh-CN-XiaoxiaoNeural", "+5%",  "+8Hz"),   # 户籍民警
}

GAP_SEC = 0.45          # 段间静音
GAP_SCENE_SEC = 0.8     # 空行段落处（未用，预留）
BASE = Path(__file__).resolve().parent.parent


def parse_script(path: Path):
    segs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        code, _, text = line.partition("]")
        code = code.strip("[]")
        if code not in VOICES:
            raise ValueError(f"未知角色代码：{code}")
        if text.strip():
            segs.append((code, text.strip()))
    return segs


async def synth_segment(code: str, text: str, out: Path, sem: asyncio.Semaphore):
    voice, rate, pitch = VOICES[code]
    async with sem:
        for attempt in range(3):
            try:
                comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                await comm.save(str(out))
                return
            except Exception as e:  # 网络抖动重试
                if attempt == 2:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
    _ = out


async def main(script_path: Path, out_path: Path) -> None:
    segs = parse_script(script_path)
    print(f"共 {len(segs)} 段，开始合成…")
    work = out_path.parent / f"_parts_{out_path.stem}"
    work.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)

    tasks = []
    for i, (code, text) in enumerate(segs):
        tasks.append(synth_segment(code, text, work / f"{i:04d}.mp3", sem))
    await asyncio.gather(*tasks)
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
                    "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
                    "-t", str(GAP_SEC), "-q:a", "9", str(gap)], check=True)

    list_file = work / "list.txt"
    lines = []
    for i in range(len(segs)):
        lines.append(f"file '{(work / f'{i:04d}.mp3').as_posix()}'")
        lines.append(f"file '{gap.as_posix()}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 重编码拼接，规避 mp3 直拼的 dts 警告
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(list_file),
                    "-c:a", "libmp3lame", "-q:a", "4", str(out_path)],
                   check=True)

    # 生成 LRC 字幕（喜马拉雅格式：[hh:mm:ss.mmm]文本；起点=前段时长+段间静音累计）
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
    lrc_path = out_path.with_suffix(".lrc")
    lrc_path.write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")

    shutil.rmtree(work, ignore_errors=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    secs = float(probe.stdout.strip() or 0)
    print(f"完成 → {out_path}（{int(secs // 60)}分{int(secs % 60):02d}秒）")


if __name__ == "__main__":
    script = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "资料" / "配音稿_第006章.txt"
    stem = script.stem.replace("配音稿_", "")
    chapter_no = stem.split("_")[0] if "_" in stem else stem
    # 音频/卷一/第006章_十八岁的巷口.mp3（章名从配音稿首段不可得，固定命名规则：第NNN章）
    title_map = {"第006章": "第006章_十八岁的巷口"}
    name = title_map.get(chapter_no, chapter_no)
    out = BASE / "音频" / "卷一" / f"{name}.mp3"
    asyncio.run(main(script, out))
