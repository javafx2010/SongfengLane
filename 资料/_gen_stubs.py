# -*- coding: utf-8 -*-
"""从 大纲/卷X_*.md 的章节表生成 正文/卷X/ 下的 272 个章节占位文件。"""
import re, os, sys

ROOT = r"E:\OneDrive\Create\锦绣前程"
VOLS = [
    ("卷一_大学保研", "卷一 大学保研", "2011—2015", "18—22岁"),
    ("卷二_职场上位", "卷二 职场上位", "2015—2020", "22—27岁"),
    ("卷三_斗争与远走", "卷三 斗争与远走", "2020—2022", "27—29岁"),
    ("卷四_异国沉沦", "卷四 异国沉沦", "2022—2024", "29—31岁"),
    ("卷五_回国接盘", "卷五 回国接盘", "2024—2029", "31—36岁"),
    ("卷六_婚内驱逐", "卷六 婚内驱逐", "2029—2033", "36—40岁"),
    ("卷七_梭哈AI", "卷七 梭哈AI", "2033—2038", "40—45岁"),
]

ACTS = {
    1: [(1,6,"第一幕 关系起点"),(7,12,"第二幕 资本变现"),(13,18,"第三幕 裂痕"),(19,24,"第四幕 被嫌弃"),(25,30,"第五幕 塌陷"),(31,36,"第六幕 卷末转折")],
    2: [(37,42,"第一幕 关系起点"),(43,48,"第二幕 资本变现"),(49,54,"第三幕 裂痕"),(55,60,"第四幕 被嫌弃"),(61,66,"第五幕 塌陷"),(67,72,"第六幕 卷末转折")],
    3: [(73,77,"第一幕 关系起点"),(78,82,"第二幕 资本变现"),(83,88,"第三幕 裂痕"),(89,93,"第四幕 被嫌弃"),(94,98,"第五幕 塌陷"),(99,104,"第六幕 卷末转折")],
    4: [(105,110,"第一幕 关系起点"),(111,116,"第二幕 资本变现"),(117,122,"第三幕 裂痕"),(123,128,"第四幕 被嫌弃"),(129,134,"第五幕 塌陷"),(135,140,"第六幕 卷末转折")],
    5: [(141,146,"第一幕 关系起点"),(147,153,"第二幕 资本变现"),(154,160,"第三幕 裂痕"),(161,166,"第四幕 被嫌弃"),(167,173,"第五幕 塌陷"),(174,180,"第六幕 卷末转折")],
    6: [(181,187,"第一幕 关系起点"),(188,195,"第二幕 资本变现"),(196,203,"第三幕 裂痕"),(204,210,"第四幕 被嫌弃"),(211,217,"第五幕 塌陷"),(218,224,"第六幕 卷末转折")],
    7: [(225,232,"第一幕 关系起点"),(233,240,"第二幕 资本变现"),(241,248,"第三幕 裂痕"),(249,256,"第四幕 被嫌弃"),(257,264,"第五幕 塌陷"),(265,272,"第六幕 卷末转折")],
}

BAD = set('\\/:*?"<>|')

def sanitize(name):
    return "".join(c for c in name if c not in BAD).strip()

def act_of(vol_no, num):
    for a, b, label in ACTS[vol_no]:
        if a <= num <= b:
            return label
    return ""

def main():
    total = 0
    missing = []
    for vi, (dirn, volname, years, ages) in enumerate(VOLS, 1):
        src = os.path.join(ROOT, "大纲", dirn.split("_")[0] + "_" + dirn.split("_", 1)[1] + ".md")
        src = os.path.join(ROOT, "大纲", dirn + ".md")
        with open(src, encoding="utf-8") as f:
            text = f.read()
        rows = {}
        for line in text.splitlines():
            m = re.match(r"^\|\s*(\d+)\s*\|(.+)\|\s*$", line)
            if not m:
                continue
            num = int(m.group(1))
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 6:
                continue
            rows[num] = cells  # [章名,类型,对手,争什么,她先出的手,代价/落点]
        outdir = os.path.join(ROOT, "正文", dirn)
        os.makedirs(outdir, exist_ok=True)
        # 校验连续性
        for n in range(min(rows), max(rows) + 1):
            if n not in rows:
                missing.append((dirn, n))
        for num in sorted(rows):
            cells = rows[num]
            title, ctype, rival, what, first_move, cost = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5]
            fn = "第%03d章_%s.md" % (num, sanitize(title))
            path = os.path.join(outdir, fn)
            content = f"""# 第{num}章 {title}

> 《锦绣前程》{volname}｜{years}｜女主{ages}

- **卷次**：{volname}（{min(rows)}—{max(rows)}章）
- **幕**：{act_of(vi, num)}
- **章类型**：{ctype}
- **写作状态**：未动笔

## 本章冲突设计

| 项目 | 内容 |
|---|---|
| 对手 | {rival} |
| 争什么 | {what} |
| 她先出的手（锚句） | {first_move} |
| 代价/落点 | {cost} |

## 写作检查清单

- [ ] 只跟一个人视角，不写全知
- [ ] 不写心理独白，只写动作；不出现"她终于明白"
- [ ] 每章至少两类冲突，结尾留一个新问题
- [ ] 如为对位章：不进她的内心，只写别人看见的她
- [ ] 如为过渡章：不推事件，只设沉默
- [ ] 如为上一代暗线：由一件物件触发，不写道德判断
- [ ] 核对该章年份/人物年龄（见 连续性/01_年表）
- [ ] 核对本卷必须露面的线索物件（见 大纲/{dirn}.md）

## 正文

（待写）
"""
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            total += 1
    ep = os.path.join(ROOT, "正文", "尾声.md")
    with open(ep, "w", encoding="utf-8", newline="\n") as f:
        f.write("""# 尾声

> 望至 2040（年表望至 2041）。一段很短的现在时。

## 内容（见 大纲/尾声与结局设计.md）

2040年深秋。公交站，两个人并排坐着，一袋橘子放在中间。周念涂着口红，问她"妈，我们什么时候能回去"。她说"很快"。车来了，她们没上。下一班还要等很久。她把橘子放在腿上，一个一个数，数到最后一个，抬头看了看天。

**定稿句**：天很蓝，蓝得像1993年那架钢琴上的漆。

- [ ] 不写她哭出声
- [ ] 不写回忆总结，过去由物件代为发言
- [ ] 不让任何人原谅她，也不让任何人替读者骂她
- [ ] 最后一页不许出现"如果"两个字

## 正文

（待写）
""")
    print("generated chapters:", total)
    print("missing rows:", missing if missing else "none")

if __name__ == "__main__":
    main()
