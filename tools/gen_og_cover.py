# -*- coding: utf-8 -*-
"""S5-A：生成全站 og:image 品牌卡（1200x630）。一次性生成，产物 assets/og-cover.png 进 git。
不进构建链（构建器不依赖 PIL），换图手动重跑本脚本。"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 630

img = Image.new("RGB", (W, H), "#0b0d12")
d = ImageDraw.Draw(img)

# 背景纵向渐变：暗底 → 顶部透一点品牌紫
for y in range(H):
    t = y / H
    r = int(11 + t * 0)
    g = int(13 + t * 0)
    b = int(18 + t * 0)
    d.line([(0, y), (W, y)], fill=(r, g, b))

# 顶部品牌色光晕（两个椭圆模糊叠加模拟 radial gradient）
glow = Image.new("RGB", (W, H), "#0b0d12")
gd = ImageDraw.Draw(glow)
gd.ellipse([250, -320, 950, 180], fill=(99, 102, 241))   # indigo
gd.ellipse([640, -260, 1320, 220], fill=(139, 92, 246))  # violet
glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(140))
img = Image.blend(img, Image.blend(img, glow, 0.55), 0.85)
d = ImageDraw.Draw(img)

def font(size, bold=True):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

f_title = font(88)
f_sub = font(38, bold=False)
f_site = font(30, bold=False)

# 标题
t1 = "群智能算法百科"
w1 = d.textlength(t1, font=f_title)
d.text(((W - w1) / 2, 170), t1, font=f_title, fill="#f7f7f8")

# 副标题（四个轴一句话）——不写实现数量：算法收录无上限，写死数字必然过时
t2 = "算法家族 × 问题库 × 方法论批评史 × 实测矩阵"
w2 = d.textlength(t2, font=f_sub)
d.text(((W - w2) / 2, 310), t2, font=f_sub, fill="#b8b9d1")

# 分隔细线
d.line([(W / 2 - 260, 415), (W / 2 + 260, 415)], fill=(99, 102, 241), width=3)

# 底部域名
t3 = "开源 · 浏览器内运行 · 结果可复现"
w3 = d.textlength(t3, font=f_site)
d.text(((W - w3) / 2, 470), t3, font=f_site, fill="#71717a")

out = os.path.join(ROOT, "assets", "og-cover.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out, "PNG", optimize=True)
print("生成", out, img.size)
