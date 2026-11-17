# -*- coding: utf-8 -*-
"""将 LRC 字幕以 USLT 歌词帧嵌入 MP3（带时间轴，播放器可直接逐行显示）。"""
import sys
from pathlib import Path

from mutagen.id3 import ID3, USLT
from mutagen.mp3 import MP3


def embed(mp3_path: Path, lrc_path: Path) -> None:
    lrc_text = lrc_path.read_text(encoding="utf-8-sig").strip()
    if not lrc_text:
        raise SystemExit(f"LRC 为空：{lrc_path}")

    audio = MP3(str(mp3_path))
    tags = audio.tags or ID3()
    # 移除旧歌词帧，避免重复
    tags.delall("USLT")
    tags.add(USLT(
        encoding=3,          # UTF-8
        lang="zho",
        desc="LRC",
        text=lrc_text,
    ))
    audio.tags = tags
    audio.save()

    # 回读校验
    check = MP3(str(mp3_path))
    uslt = check.tags.getall("USLT")
    if not uslt:
        raise SystemExit("嵌入失败：未找到 USLT 帧")
    print(f"完成 → {mp3_path}")
    print(f"歌词帧：{len(uslt)} 个，正文 {len(uslt[0].text)} 字符")


if __name__ == "__main__":
    mp3 = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"e:\OneDrive\Create\松风巷的女儿\音频\卷一\第001章_十八岁的巷口.mp3")
    lrc = Path(sys.argv[2]) if len(sys.argv) > 2 else mp3.with_suffix(".lrc")
    embed(mp3, lrc)
