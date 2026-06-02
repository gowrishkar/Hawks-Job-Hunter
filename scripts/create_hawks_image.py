#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "hawks-job-hunter-card.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 1600, 900
img = Image.new("RGB", (W, H), "#070A12")
d = ImageDraw.Draw(img)

# Background: deep navy with subtle gradient
for y in range(H):
    t = y / (H - 1)
    r = int(7 + 12 * t)
    g = int(10 + 18 * t)
    b = int(18 + 35 * t)
    d.line([(0, y), (W, y)], fill=(r, g, b))

# Grid / scanning lines
for x in range(-200, W + 200, 72):
    d.line([(x, 0), (x + 460, H)], fill=(28, 44, 76), width=1)
for y in range(80, H, 80):
    d.line([(0, y), (W, y)], fill=(20, 31, 55), width=1)

# Soft glows
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse((900, -260, 1900, 760), fill=(26, 114, 255, 55))
gd.ellipse((-240, 390, 600, 1190), fill=(245, 180, 52, 34))
glow = glow.filter(ImageFilter.GaussianBlur(70))
img = Image.alpha_composite(img.convert("RGBA"), glow)
d = ImageDraw.Draw(img)

# Typography helpers
def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

f_title = font(108, True)
f_sub = font(42, False)
f_tag = font(34, True)
f_small = font(29, False)

# Fixed Hawks logo mark: geometric hawk head, not a broken/placeholder text logo
cx, cy = 255, 290
scale = 1.0
shadow = [(126, 176), (408, 244), (322, 336), (436, 395), (276, 392), (207, 507), (196, 377), (82, 335)]
d.polygon([(x+10, y+16) for x,y in shadow], fill=(0, 0, 0, 105))
# main gold head
head = [(126, 176), (408, 244), (322, 336), (436, 395), (276, 392), (207, 507), (196, 377), (82, 335)]
d.polygon(head, fill=(245, 178, 45, 255))
# dark cut for beak/neck
beak_cut = [(322, 336), (436, 395), (326, 389), (276, 360)]
d.polygon(beak_cut, fill=(12, 18, 32, 255))
# blue wing/forehead accent
accent = [(126, 176), (408, 244), (222, 258), (82, 335)]
d.polygon(accent, fill=(52, 130, 255, 255))
# white face plane
face = [(204, 255), (326, 267), (276, 325), (158, 331)]
d.polygon(face, fill=(238, 244, 255, 255))
# eye
d.ellipse((264, 282, 287, 305), fill=(6, 9, 15, 255))
d.polygon([(282, 287), (309, 276), (292, 300)], fill=(6, 9, 15, 255))
# crisp outlines
d.line(head + [head[0]], fill=(255, 211, 98, 255), width=5)
d.line(accent + [accent[0]], fill=(124, 184, 255, 255), width=3)

# Title and copy
x0 = 520
d.text((x0, 188), "HAWKS", font=f_title, fill=(245, 178, 45, 255))
d.text((x0, 305), "JOB HUNTER", font=f_title, fill=(238, 244, 255, 255))
d.text((x0, 450), "Scout as Code for high-trust AI-role discovery", font=f_sub, fill=(174, 193, 224, 255))

# Pills
pill_y = 575
pills = ["retrieve", "validate", "score", "dedupe", "JSON"]
x = x0
for pill in pills:
    bbox = d.textbbox((0,0), pill.upper(), font=f_tag)
    tw = bbox[2]-bbox[0]
    pad_x, pad_y = 24, 13
    rect = (x, pill_y, x + tw + pad_x*2, pill_y + 58)
    d.rounded_rectangle(rect, radius=29, fill=(12, 24, 46, 235), outline=(62, 136, 255, 210), width=2)
    d.text((x+pad_x, pill_y+10), pill.upper(), font=f_tag, fill=(220, 235, 255, 255))
    x = rect[2] + 18

# Bottom statement
d.text((82, 792), "Principle: fewer strong matches > many weak matches", font=f_small, fill=(245, 178, 45, 255))
d.text((1115, 792), "github.com/gowrishkar/Hawks-Job-Hunter", font=f_small, fill=(156, 179, 215, 255))

# Border
d.rounded_rectangle((36, 36, W-36, H-36), radius=42, outline=(86, 155, 255, 130), width=3)

img.convert("RGB").save(OUT, quality=95, optimize=True)
print(OUT)
