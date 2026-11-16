# -*- coding: utf-8 -*-
"""在选定封面上排版竖排书名，输出定稿图。可重复运行。

用法：python 资料/add_cover_title.py
依赖：Pillow（PIL）。
输入：封面/cover_001_插画_seed804097194_.png（定稿底图）
输出：封面/封面_定稿.png
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
SRC = BASE_DIR / "封面" / "cover_001_插画_seed804097194_.png"
DST = BASE_DIR / "封面" / "封面_定稿.png"

TITLE_FONT = r"C:\Windows\Fonts\STXINGKA.TTF"   # 华文行楷
SEAL_FONT = r"C:\Windows\Fonts\simkai.ttf"      # 楷体（印章字）

TITLE = "松风巷的女儿"
SEAL_CHAR = "梅"          # 朱印：女主之名
TEXT_COLOR = (245, 240, 230)
EDGE_COLOR = (25, 18, 12)


def draw_vertical_text(img: Image.Image) -> None:
    w, h = img.size
    font_size = int(w * 0.115)
    font = ImageFont.truetype(TITLE_FONT, font_size)
    step = int(font_size * 1.02)
    x = int(w * 0.885)                     # 竖排右缘，压右上暗区
    y0 = int(h * 0.055)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    y = y0
    for ch in TITLE:
        bbox = d.textbbox((0, 0), ch, font=font)
        cx = x - (bbox[2] - bbox[0]) // 2 - bbox[0]
        d.text((cx, y), ch, font=font, fill=TEXT_COLOR,
               stroke_width=max(2, font_size // 28), stroke_fill=EDGE_COLOR)
        y += step

    # 朱印：书名末端下方
    seal_size = int(w * 0.085)
    sx = x - seal_size // 2
    sy = y + int(font_size * 0.15)
    d.rounded_rectangle((sx, sy, sx + seal_size, sy + seal_size),
                        radius=seal_size // 8, fill=(176, 48, 38, 235))
    sfont = ImageFont.truetype(SEAL_FONT, int(seal_size * 0.72))
    sb = d.textbbox((0, 0), SEAL_CHAR, font=sfont)
    d.text((sx + (seal_size - (sb[2] - sb[0])) // 2 - sb[0],
            sy + (seal_size - (sb[3] - sb[1])) // 2 - sb[1]),
           SEAL_CHAR, font=sfont, fill=(248, 242, 230, 255))

    # 投影层，轻移合成
    shadow = layer.filter(ImageFilter.GaussianBlur(4))
    img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 90)), )
    img.alpha_composite(shadow, (3, 5))
    img.alpha_composite(layer)


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    draw_vertical_text(img)
    img.convert("RGB").save(DST, quality=95)
    print(f"定稿已输出 → {DST}")


if __name__ == "__main__":
    main()
