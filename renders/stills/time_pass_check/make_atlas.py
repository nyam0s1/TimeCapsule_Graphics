"""Year-label atlas for the on-screen counter: one row per year, bottom row = first year. Designed for 1920x1080."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
out, y0, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
W, H = 224, 80
font = ImageFont.truetype(r'C:\Windows\Fonts\bahnschrift.ttf', 56)
atlas = Image.new('RGBA', (W, H * n), (0, 0, 0, 0))
for i in range(n):
    txt = str(y0 + i)
    sh = Image.new('L', (W, H), 0); d = ImageDraw.Draw(sh); d.text((W - 14, H // 2 + 2), txt, font=font, fill=255, anchor='rm')
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    row = Image.new('RGBA', (W, H), (0, 0, 0, 0)); row.putalpha(sh.point(lambda v: int(v * 0.62)))
    fg = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fg); d.text((W - 14, H // 2), txt, font=font, fill=(255, 255, 255, 235), anchor='rm')
    row = Image.alpha_composite(row, fg)
    atlas.paste(row, (0, H * (n - 1 - i)))
atlas.save(out); print('atlas', atlas.size)
