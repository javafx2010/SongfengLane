# -*- coding: utf-8 -*-
"""扫描全书正文的每章出场人物，解析大纲章节表，生成：
1. 资料/章节出场索引.json
2. 架构设计/人物章节出场索引.html（按章节索引，可按人物筛选）
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
NAMES = ["苏冬梅", "苏冬生", "周惠兰", "苏德海", "徐远山", "程永年", "苏万山", "丁桂宁",
         "陈九", "周守青", "顾怀山", "钱仲文", "马库斯", "许家平", "姜采薇", "温以苓",
         "叶曼君", "顾晓梅", "林小满", "岑青桐", "周念", "苏嘉禾", "徐卫东", "程雪见",
         "江晚棠", "祁予真", "胖丫", "老校长", "李婶", "六婆"]
# 代称 → 本名（仅在她/他们视角的主线章应用，避免对位章误判）
ROLE_ALIAS = {"母亲": "周惠兰", "父亲": "苏德海", "弟弟": "苏冬生", "爷爷": "苏万山", "祖父": "苏万山"}
# 卷一人物线指定（大纲/卷一_大学保研.md「人物线与交集设计」）：按章补入必须出场的人物
EXTRA_CAST = {
    "6": ["顾晓梅", "林小满", "叶曼君"],   # 同巷三岔起点，三女孩同框
    "26": ["徐远山", "周惠兰"],            # 球鞋与"企业资助"，两个匿名父亲的线交叉
}

# ---- 1) 解析大纲章节表 ----
chapter_meta = {}  # ch(str) -> dict
vol_files = sorted((BASE / "大纲").glob("卷*_*.md"))
for vf in vol_files:
    text = vf.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7 or not cells[0].isdigit():
            continue
        chapter_meta[cells[0].lstrip("0") or "0"] = {
            "title": cells[1], "type": cells[2], "opp": cells[3],
            "goal": cells[4], "move": cells[5], "cost": cells[6],
        }

# ---- 2) 扫描正文出场人物 ----
chapters = []
vol_dirs = sorted((BASE / "章节").glob("卷*"))
vol_index = {d.name: i + 1 for i, d in enumerate(vol_dirs)}
for vd in vol_dirs:
    for chdir in sorted(d for d in vd.iterdir() if d.is_dir() and d.name.startswith("第")):
        m = re.match(r"第(\d+)章_(.+)", chdir.name)
        ch, title = m.group(1).lstrip("0"), m.group(2)
        md = chdir / f"{chdir.name}.md"
        text = md.read_text(encoding="utf-8")
        meta = chapter_meta.get(ch, {})
        is_counterpoint = "对位" in meta.get("type", "")
        cast = [n for n in NAMES if n in text]
        if not is_counterpoint:
            for alias, real in ROLE_ALIAS.items():
                if alias == "弟弟" and int(ch) < 2:
                    continue  # 第1章弟弟尚未出生
                if real not in cast and alias in text:
                    cast.append(real)
        # 对手字段若为人名则计入；苏冬梅不强制列入——以「视角」字段表达
        for n in NAMES:
            if n != "苏冬梅" and n not in cast and meta.get("opp", "") and n in meta["opp"]:
                cast.append(n)
        for n in EXTRA_CAST.get(ch, []):
            if n not in cast:
                cast.append(n)
        pov = not is_counterpoint  # True=她的视角章；False=对位章（她只"被看见"）
        # 按出场顺序稳定排序（苏冬梅置顶）
        cast = sorted(set(cast), key=lambda n: (n != "苏冬梅", NAMES.index(n) if n in NAMES else 99))
        chapters.append({
            "ch": int(ch), "vol": vol_index[vd.name], "volName": vd.name,
            "title": title, "type": meta.get("type", ""), "opp": meta.get("opp", ""),
            "goal": meta.get("goal", ""), "move": meta.get("move", ""), "cost": meta.get("cost", ""),
            "cast": cast, "pov": pov,
        })
# 尾声
ep = BASE / "章节" / "尾声.md"
if ep.exists():
    text = ep.read_text(encoding="utf-8")
    cast = sorted({n for n in NAMES if n in text} | {"苏冬梅"},
                  key=lambda n: (n != "苏冬梅", NAMES.index(n) if n in NAMES else 99))
    chapters.append({"ch": 273, "vol": 8, "volName": "尾声", "title": "尾声", "type": "尾声",
                     "opp": "", "goal": "", "move": "", "cost": "", "cast": cast, "pov": True})

chapters.sort(key=lambda c: c["ch"])
out = {"names": NAMES, "chapters": chapters}
(BASE / "资料" / "章节出场索引.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"chapters: {len(chapters)}, meta: {len(chapter_meta)}")

# ---- 3) 生成 HTML ----
COLORS = {
    "苏冬梅": "#e8b4b8", "周惠兰": "#e0a458", "苏德海": "#e0a458", "苏冬生": "#e0a458",
    "徐远山": "#e0a458", "程永年": "#e0a458", "苏万山": "#e0a458", "丁桂宁": "#e0a458",
    "陈九": "#6f9ceb", "周守青": "#6f9ceb", "顾怀山": "#6f9ceb", "钱仲文": "#6f9ceb",
    "马库斯": "#6f9ceb", "许家平": "#6f9ceb", "姜采薇": "#c9a0dc", "温以苓": "#c9a0dc",
    "祁予真": "#c9a0dc", "叶曼君": "#7fc8a9", "顾晓梅": "#7fc8a9", "林小满": "#7fc8a9",
    "岑青桐": "#7fc8a9", "江晚棠": "#7fc8a9", "周念": "#f2d0a4", "苏嘉禾": "#f2d0a4",
    "徐卫东": "#f2d0a4", "程雪见": "#f2d0a4", "胖丫": "#b8b2a4", "老校长": "#b8b2a4",
    "李婶": "#b8b2a4", "六婆": "#b8b2a4",
}
VOL_TITLES = {
    1: ("卷一 · 大学保研", "第1—36章 ｜ 序幕1998—2011／正篇2011—2015"),
    2: ("卷二 · 职场上位", "第37—72章 ｜ 2016—2019"),
    3: ("卷三 · 斗争与远走", "第73—104章 ｜ 2020—2022"),
    4: ("卷四 · 异国沉沦", "第105—140章 ｜ 2023—2024"),
    5: ("卷五 · 回国接盘", "第141—180章 ｜ 2025—2029"),
    6: ("卷六 · 婚内驱逐", "第181—224章 ｜ 2030—2032"),
    7: ("卷七 · 梭哈AI", "第225—272章 ｜ 2033—2038"),
    8: ("尾声", "第273章 ｜ 2039—2041"),
}
# 每卷家庭线变化（源自 连续性/01_人物事件年表）
VOL_FAMILY = {
    1: "1993 冬梅出生，德海起疑 → 1996 德海算明白冬梅是亲女 → 1998 「再要一个」 → 1999 冬生出生·丢公职退房·搬回老宅 → 2001/2003 楼房铺面过户苏万山 → 2004 抓奸·亲子鉴定·离婚净身出户（孩子与老宅归周惠兰，无抚养费，一刀两断） → 2008 苏嘉禾出生",
    2: "程永年与徐远山「平摊成本」供养姐弟 → 2018 周惠兰第一次堵徐远山的车 → 2019 苏万山第一次中风",
    3: "家里只肯供弟弟（退学根源） → 2022 远走出国，与苏家渐行渐远",
    4: "依附马库斯 → 2024 两次流产、早产生下周念；母亲飞去抱孩子回国，对外称帮亲戚带娃",
    5: "温以苓包装「海外精英」回国 → 2028 嫁许家平，徐卫东喊她「姐」 → 2029 苏万山去世",
    6: "「家暴」叙事铺开 → 2031 程永年病重、周惠兰留纸离开 → 2032 周惠兰拿钱走人，程雪见接手程氏",
    7: "2033 拆迁公告·程永年入狱 → 2035 开庭 → 2036 周惠兰病逝·程永年出狱·抵押老宅梭哈AI → 2037 程永年死·陈九死 → 2038 崩盘·苏德海隔玻璃叫「梅梅」",
    8: "母女相依：四本账第一次放进同一只抽屉",
}
data_js = json.dumps(out, ensure_ascii=False)
colors_js = json.dumps(COLORS, ensure_ascii=False)
vols_js = json.dumps(VOL_TITLES, ensure_ascii=False)
fam_js = json.dumps(VOL_FAMILY, ensure_ascii=False)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>《松风巷的女儿》章节出场人物索引</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#0e0f13; color:#d8d3c8; font-family:"Microsoft YaHei","PingFang SC",sans-serif; }
  header { padding:34px 0 8px; text-align:center; }
  header h1 { font-size:25px; color:#e8b4b8; letter-spacing:2px; }
  header p { color:#8a8578; font-size:13px; margin-top:8px; }
  header a { color:#e8b4b8; font-size:13px; }
  #charBar { display:flex; flex-wrap:wrap; justify-content:center; gap:7px; padding:14px 24px 4px; }
  .chip { background:#1a1c24; border:1px solid #343848; color:#b8b2a4; border-radius:16px; padding:5px 12px; font-size:12.5px; cursor:pointer; transition:.15s; }
  .chip:hover { border-color:#e8b4b8; color:#fff; }
  .chip.active { background:#e8b4b8; border-color:#e8b4b8; color:#14161d; font-weight:bold; }
  #stats { text-align:center; color:#5a5850; font-size:12px; padding:6px 0 14px; }
  #vols { max-width:960px; margin:0 auto; padding:0 20px 80px; }
  .vol-head { border-left:4px solid #e8b4b8; background:#14161d; border-radius:0 10px 10px 0; padding:12px 20px; margin:26px 0 12px; }
  .vol-head h2 { font-size:18px; color:#e8b4b8; }
  .vol-head .meta { font-size:12.5px; color:#8a8578; margin-top:4px; }
  .chap { background:#14161d; border:1px solid #262935; border-radius:10px; padding:11px 16px; margin-bottom:9px; transition:.15s; }
  .chap:hover { border-color:#3d4152; }
  .chap.dim { opacity:.25; }
  .chap .row1 { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  .chap .num { font-weight:bold; color:#e0a458; font-size:13.5px; }
  .chap .t { font-size:15px; color:#d8d3c8; font-weight:bold; }
  .chap .tp { font-size:10.5px; color:#7fc8a9; border:1px solid #7fc8a955; border-radius:9px; padding:0 7px; }
  .chap .row2 { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:7px; }
  .tag { display:inline-block; font-size:11.5px; padding:2px 9px; border-radius:10px; cursor:pointer; }
  .tag:hover { filter:brightness(1.3); }
  .povtag { font-size:11px; padding:2px 9px; border-radius:10px; background:#e8b4b814; color:#c9a3a6; border:1px dashed #e8b4b855; }
  .povtag.seen { background:#7fc8a914; color:#7fc8a9; border-color:#7fc8a955; }
  .none { color:#5a5850; font-size:12px; }
  .chap .sum { font-size:12.5px; line-height:1.8; color:#9a958a; margin-top:7px; }
  .chap .sum b { color:#c9c3b5; font-weight:normal; }
  .chap .sum .lbl { color:#5a5850; }
  .hidden { display:none; }
  .famline { font-size:12.5px; line-height:1.9; color:#c8a468; background:#e0a4580d; border:1px dashed #e0a45844; border-radius:8px; padding:8px 14px; margin-top:8px; }
  .famline .lbl { color:#8a8578; }
</style>
</head>
<body>
<header>
  <h1>章节出场人物索引</h1>
  <p>按章节索引：每章列出<b>出场人物</b>与<b>主要故事事件</b>（对手／争什么／落点） ｜ 苏冬梅不再是核心人物，仅以「视角」标注淡化 ｜ 卷头有「家庭线」变化带 ｜ 点击人物名可过滤其出场章节 ｜ 数据源：<code>资料\\章节出场索引.json</code></p>
  <p><a href="人物分卷出场表.html">← 分卷出场人物与主要事件</a>　<a href="人物历史事件年表.html">← 人物历史事件年表</a></p>
</header>
<div id="charBar"></div>
<div id="stats"></div>
<div id="vols"></div>
<script>
const DATA = __DATA__;
const COLORS = __COLORS__;
const VOLS = __VOLS__;
const FAM = __FAM__;
const bar = document.getElementById("charBar");
const stats = document.getElementById("stats");
let active = null;

// 顶部人物条：除苏冬梅外出场人物 + 苏冬梅（视角）
const present = [...new Set(DATA.chapters.flatMap(c => c.cast))].filter(n => n !== "苏冬梅");
present.unshift("苏冬梅");
present.forEach(n => {
  const c = document.createElement("span");
  c.className = "chip";
  c.textContent = n;
  c.dataset.n = n;
  c.style.borderColor = (COLORS[n] || "#8a8578") + "66";
  c.onclick = () => setFilter(n);
  bar.appendChild(c);
});
const clear = document.createElement("span");
clear.className = "chip";
clear.textContent = "全部";
clear.onclick = () => { active = null; bar.querySelectorAll(".chip").forEach(x => x.classList.remove("active")); apply(); };
bar.prepend(clear);

// 人物过滤（chips 与人物卡标题共用）
function setFilter(n) {
  active = (active === n) ? null : n;
  bar.querySelectorAll(".chip").forEach(x => x.classList.toggle("active", x.dataset.n === active));
  apply();
}

// 按章节渲染：每章＝出场人物＋主要故事事件
const volsEl = document.getElementById("vols");
let lastVol = 0, container = null;
DATA.chapters.forEach(ch => {
  if (ch.vol !== lastVol) {
    const head = document.createElement("div");
    head.className = "vol-head";
    head.innerHTML = `<h2>${VOLS[ch.vol][0]}</h2><div class="meta">${VOLS[ch.vol][1]}</div>
      <div class="famline"><span class="lbl">家庭线：</span>${FAM[ch.vol]}</div>`;
    container = document.createElement("div");
    container.className = "volbody";
    volsEl.appendChild(head);
    volsEl.appendChild(container);
    lastVol = ch.vol;
  }
  const d = document.createElement("div");
  d.className = "chap";
  d.dataset.ch = ch.ch;
  const tags = ch.cast.map(n => {
    const col = COLORS[n] || "#8a8578";
    return `<span class="tag" data-n="${n}" style="background:${col}22;color:${col};border:1px solid ${col}55">${n}</span>`;
  }).join("");
  const pov = ch.pov
    ? `<span class="povtag" data-n="苏冬梅">视角 · 苏冬梅</span>`
    : `<span class="povtag seen" data-n="苏冬梅">被看见 · 苏冬梅</span>`;
  const none = ch.cast.length ? "" : `<span class="none">（本章无其他具名人物）</span>`;
  const sum = (ch.opp ? `<span class="lbl">对手：</span><b>${ch.opp}</b>　<span class="lbl">争：</span><b>${ch.goal}</b>　<span class="lbl">落：</span><b>${ch.cost}</b>` : "");
  d.innerHTML = `
    <div class="row1">
      <span class="num">第${String(ch.ch).padStart(3,"0")}章</span>
      <span class="t">${ch.title}</span>
      ${ch.type && ch.type !== "主线" && ch.type !== "尾声" ? `<span class="tp">${ch.type}</span>` : ""}
    </div>
    <div class="row2">${tags}${none}${pov}</div>
    ${sum ? `<div class="sum">${sum}</div>` : ""}`;
  d.querySelectorAll(".tag").forEach(t => t.onclick = () => setFilter(t.dataset.n));
  container.appendChild(d);
});

function apply() {
  let shown = 0;
  document.querySelectorAll(".chap").forEach(el => {
    const ch = DATA.chapters.find(c => c.ch === +el.dataset.ch);
    const hit = active && (ch.cast.includes(active) || (active === "苏冬梅" && ch.pov));
    el.classList.toggle("dim", !!active && !hit);
    el.classList.toggle("hidden", !!active && !hit);
    if (!active || hit) shown++;
  });
  document.querySelectorAll(".volbody").forEach(b => {
    b.classList.toggle("hidden", !!active && ![...b.children].some(x => !x.classList.contains("hidden")));
  });
  document.querySelectorAll(".vol-head").forEach(h => {
    h.classList.toggle("hidden", !!active && h.nextElementSibling.classList.contains("hidden"));
  });
  stats.textContent = active ? `${active}：${active === "苏冬梅" ? "视角贯穿" : "出场"} ${shown} 章` : `共 ${DATA.chapters.length} 章`;
}
apply();
</script>
</body>
</html>
"""
html = html.replace("__DATA__", data_js).replace("__COLORS__", colors_js).replace("__VOLS__", vols_js).replace("__FAM__", fam_js)
out_html = BASE / "架构设计" / "人物章节出场索引.html"
out_html.write_text(html, encoding="utf-8")
print("html:", out_html, f"{out_html.stat().st_size // 1024} KB")
