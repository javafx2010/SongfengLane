# -*- coding: utf-8 -*-
"""把子代理接力产出的章节草稿导入章节 md（追加模式）。

用法：
  python import_agent_draft.py <task_output.txt> <chapter.md> <章号> [init|append|finalize]

提取规则：
  1. 优先 <<正文开始>> ... <<正文结束>>；
  2. 回退：从 "## 正文"（或【第一部分】）起，至 "（第N章完）" 或 "## 完成报告"/"请你注意" 之前止。

模式：
  init    —— 正文为（待写）时整段替换，末尾加【待续】
  append  —— 把末尾的【待续】替换为本次草稿，末尾再加【待续】（若草稿含（第N章完）则不加，并转入 finalize）
  finalize—— 只做元数据收尾（状态行＋清单勾选），并报告字数
"""
import re
import sys
from pathlib import Path

META_CUTS = ("## 完成报告", "请你注意", "## 说明", "**请你注意**")

def clean(text: str) -> str:
    text = text.replace("**", "")
    text = re.sub(r"^#{1,4}\s.*$", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s.*$", "", text, flags=re.M)
    text = re.sub(r"^```.*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract(raw: str, no: int, nodiv: bool = False) -> str:
    m = re.search(r"<<正文开始>>(.*?)<<正文结束>>", raw, re.S)
    body = m.group(1) if m else raw
    if not m:
        starts = [mm.start() for pat in (r"^##\s*正文.*$", r"^\s*【第一部分】\s*$") for mm in [re.search(pat, raw, re.M)] if mm]
        if starts:
            body = raw[min(starts):]
        for cut in META_CUTS:
            i = body.find(cut)
            if i > 500:
                body = body[:i]
        end = re.search(rf"（第{no}章完）", body)
        if end:
            body = body[: end.end()]
    body = clean(body)
    body = re.sub(r"^\s*【第[一二三四1234]部分】\s*$", "", body, flags=re.M).strip()
    if nodiv:
        mm = re.search(r"^\s*＊[\s　]*＊[\s　]*＊\s*$", body, flags=re.M)
        if mm:
            body = body[: mm.start()].rstrip()
    return body

def finalize(md: str, no: int) -> str:
    md = re.sub(r"- \*\*写作状态\*\*：.*",
                "- **写作状态**：已完稿（视点配比、章长按设计优化新纪律核对）", md)
    md = md.replace("- [ ] ", "- [x] ")
    return md

def main():
    src, md_path, no = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    mode = sys.argv[4] if len(sys.argv) > 4 else "append"
    nodiv = len(sys.argv) > 5 and sys.argv[5] == "nodiv"
    md = md_path.read_text(encoding="utf-8")

    if mode == "finalize":
        md = finalize(md, no)
        md_path.write_text(md, encoding="utf-8", newline="\n")
        _report(md, no, "收尾完成")
        return

    raw = Path(src).read_text(encoding="utf-8", errors="replace")
    body = raw if mode == "appendfile" else extract(raw, no, nodiv)
    done = f"（第{no}章完）" in body
    if mode == "init" or "（待写）" in md:
        if "## 正文" in md:
            idx = md.find("## 正文")
            md = md[:idx] + "## 正文\n\n" + body
        else:
            md += "\n## 正文\n\n" + body
    elif mode == "insert":
        mm = re.search(r"^\s*＊[\s　]*＊[\s　]*＊\s*$", md, flags=re.M)
        if not mm:
            raise SystemExit("章节文件无分隔线，无法插入")
        md = md[: mm.start()] + body + "\n\n＊　＊　＊" + md[mm.end():]
    else:
        if "【待续】" not in md:
            raise SystemExit("章节文件无【待续】续写点，无法追加")
        md = md.replace("【待续】", body, 1)
    if done:
        md = finalize(md, no)
    else:
        md = md.rstrip() + "\n\n【待续】\n"
    md_path.write_text(md, encoding="utf-8", newline="\n")
    _report(md, no, "收稿完成" if done else "追加完成")

def _report(md, no, tag):
    i = md.find("## 正文")
    seg = md[i:] if i != -1 else md
    han = len(re.findall(r"[\u4e00-\u9fff]", seg))
    print(f"[D{no}] {tag} body_han={han}")
    if han < 8000:
        print(f"[!] short of 8000 by {8000 - han}")

if __name__ == "__main__":
    main()
