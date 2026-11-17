import json, re, os
from pathlib import Path

BASE = Path(r"E:/OneDrive/Create/松风巷的女儿")
NOTE = BASE / "资料/_sync_tmp/note_v3.txt"
text = NOTE.read_text(encoding="utf-8")

# --- parse chapter prose from note (first occurrence of each chapter number) ---
pat = re.compile(r"第(\d+)章\s+([^\n：:]{1,40})[：:]\s*([^\n]*)")
outlines = {}
for m in pat.finditer(text):
    n = int(m.group(1))
    if n not in outlines:
        outlines[n] = {"title": m.group(2).strip(), "prose": m.group(3).strip()}
assert len(outlines) == 272, len(outlines)

# --- new volume-one chapter map (note prose section = new numbering) ---
# old ch1 -> new ch6 (already renamed); old ch2 -> new ch3; old ch3 -> new ch5
# old ch4/5/6 archived; new ch1/2/4 are new chapters.
VOL1 = {
    1: ("一九九八年的夏天", "第一幕 关系起点", "主线"),
    2: ("弟弟出生那天", "第一幕 关系起点", "主线"),
    3: ("钢琴抬下楼", "第一幕 关系起点", "主线"),
    4: ("巷子里的第一夜", "第一幕 关系起点", "主线"),
    5: ("巷子里的十二年", "第一幕 关系起点", "主线"),
    6: ("十八岁的巷口", "第一幕 关系起点", "主线"),
}

VOL_DIR = {
    1: "卷一_大学保研", 2: "卷二_职场上位", 3: "卷三_斗争与远走",
    4: "卷四_异国沉沦", 5: "卷五_回国接盘", 6: "卷六_婚内驱逐", 7: "卷七_梭哈AI",
}

def vol_of(n):
    return 1 if n <= 36 else 2 if n <= 72 else 3 if n <= 104 else 4 if n <= 140 else 5 if n <= 180 else 6 if n <= 224 else 7

def find_chapter_file(n):
    d = BASE / "正文" / VOL_DIR[vol_of(n)]
    hits = list(d.glob(f"第{n:03d}章_*.md"))
    if not hits:
        hits = list(d.glob(f"第{n}章_*.md"))
    return hits[0] if hits else None

def write_text(p, s):
    p.write_text(s, encoding="utf-8")

# --- create three new prologue chapters ---
NEW_TPL = """# 第{n}章 {title}

> 《松风巷的女儿》卷一 大学保研｜序幕1998—2011｜女主6—22岁

- **卷次**：卷一 大学保研（1—36章）
- **幕**：{act}
- **章类型**：{ctype}
- **写作状态**：未动笔

## 本章冲突设计

| 项目 | 内容 |
|---|---|
| 对手 | （待补） |
| 争什么 | （待补） |
| 她先出的手（锚句） | （待补） |
| 代价/落点 | （待补） |

## 细纲（ima v3）

{prose}

## 写作检查清单

- [ ] 只跟一个人视角，不写全知
- [ ] 不写心理独白，只写动作；不出现"她终于明白"
- [ ] 每章至少两类冲突，结尾留一个新问题
- [ ] 如为对位章：不进她的内心，只写别人看见的她
- [ ] 如为过渡章：不推事件，只设沉默
- [ ] 如为上一代暗线：由一件物件触发，不写道德判断
- [ ] 核对该章年份/人物年龄（见 连续性/01_年表）
- [ ] 核对本卷必须露面的线索物件（见 大纲/卷一_大学保研.md）

## 正文

（待写）
"""

for n in (1, 2, 4):
    title, act, ctype = VOL1[n]
    p = BASE / "正文" / "卷一_大学保研" / f"第{n:03d}章_{title}.md"
    write_text(p, NEW_TPL.format(n=n, title=title, act=act, ctype=ctype, prose=outlines[n]["prose"]))
    print("CREATED", p.name)

# --- update renumbered chapter files header/title, insert/replace 细纲 ---
RENAME_TITLE = {3: "钢琴抬下楼", 5: "巷子里的十二年", 6: "十八岁的巷口"}
for n in (3, 5, 6):
    p = find_chapter_file(n)
    assert p, n
    s = p.read_text(encoding="utf-8")
    title = RENAME_TITLE[n]
    # rename file if title differs
    want = BASE / "正文" / "卷一_大学保研" / f"第{n:03d}章_{title}.md"
    s = re.sub(r"^# 第\d+章 .+$", f"# 第{n}章 {title}", s, count=1, flags=re.M)
    s = re.sub(r"^- \*\*幕\*\*：.*$", f"- **幕**：{VOL1[n][1]}", s, count=1, flags=re.M)
    s = re.sub(r"^- \*\*章类型\*\*：.*$", f"- **章类型**：{VOL1[n][2]}", s, count=1, flags=re.M)
    # replace/add 细纲 section
    outline = outlines[n]["prose"]
    sec = f"## 细纲（ima v3）\n\n{outline}\n\n"
    if re.search(r"^## 细纲.*$", s, flags=re.M):
        s = re.sub(r"^## 细纲[^\n]*\n\n(?:.*\n)*?(?=^## 写作检查清单)", sec, s, count=1, flags=re.M)
    else:
        s = re.sub(r"(?=^## 写作检查清单)", sec, s, count=1, flags=re.M)
    if p != want:
        p.rename(want)
    write_text(want, s)
    print("UPDATED", want.name)

# --- insert 细纲 into all other chapter files (skip 1-6 done above) ---
inserted, skipped = 0, 0
for n in range(1, 273):
    if n <= 6:
        continue
    p = find_chapter_file(n)
    if not p:
        print("MISSING FILE FOR", n)
        continue
    s = p.read_text(encoding="utf-8")
    if re.search(r"^## 细纲", s, flags=re.M):
        skipped += 1
        continue
    outline = outlines[n]["prose"]
    if not outline:
        print("EMPTY OUTLINE", n)
        continue
    sec = f"## 细纲（ima v3）\n\n{outline}\n\n"
    s = re.sub(r"(?=^## 写作检查清单)", sec, s, count=1, flags=re.M)
    write_text(p, s)
    inserted += 1
print("INSERTED", inserted, "SKIPPED", skipped)

# save parsed data for audit
out = BASE / "资料/_sync_tmp/chapter_outlines.json"
out.write_text(json.dumps(outlines, ensure_ascii=False, indent=2), encoding="utf-8")
print("AUDIT JSON", out)
