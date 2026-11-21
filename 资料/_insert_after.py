# -*- coding: utf-8 -*-
"""把扩写段按锚点插入章节 md。

用法：python _insert_after.py <expand.txt> <chapter.md>

expand.txt 内含一个或多个段：
  <<正文开始>>
  【插入点】正文中已有的一句原句（锚点，须唯一）
  <空行>
  新内容若干段
  <<正文结束>>

规则：在 md 中定位锚点所在段，把新内容插入该段之后。
"""
import re
import sys
from pathlib import Path

src, md_path = Path(sys.argv[1]), Path(sys.argv[2])
raw = src.read_text(encoding="utf-8")
md = md_path.read_text(encoding="utf-8")

segs = re.findall(r"<<正文开始>>(.*?)<<正文结束>>", raw, re.S)
if not segs:
    raise SystemExit("未找到 <<正文开始>> 段")

for seg in segs:
    seg = seg.strip()
    m = re.match(r"【插入点】(.+)", seg)
    if not m:
        raise SystemExit("段首缺【插入点】锚句")
    anchor = m.group(1).strip()
    body = seg[m.end():].strip()
    i = md.find(anchor)
    if i == -1:
        raise SystemExit(f"锚点未找到：{anchor[:30]}...")
    if md.count(anchor) != 1:
        raise SystemExit(f"锚点不唯一（{md.count(anchor)}处）：{anchor[:30]}...")
    j = md.find("\n\n", i + len(anchor))
    if j == -1:
        raise SystemExit("锚点后无段落边界")
    md = md[:j] + "\n\n" + body + md[j:]

md_path.write_text(md, encoding="utf-8", newline="\n")
i = md.find("## 正文")
seg2 = md[i:] if i != -1 else md
seg2 = re.sub(r"【待续】|（第\d+章完）", "", seg2)
han = len(re.findall(r"[\u4e00-\u9fff]", seg2))
print(f"[OK] 插入{len(segs)}段, body_han={han}")
if han < 8000:
    print(f"[!] short of 8000 by {8000 - han}")
