"""Flood-fill the outer white background of the Propto logo to transparent,
preserving the emblem's internal white details."""
from PIL import Image, ImageDraw
import sys

SRC = "/app/frontend/public/propto-logo.png"
OUT = "/app/frontend/public/propto-logo.png"
MARKER = (255, 0, 255)
THRESH = 60

im = Image.open(SRC).convert("RGB")
w, h = im.size
corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
           (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
for c in corners:
    try:
        ImageDraw.floodfill(im, c, MARKER, thresh=THRESH)
    except Exception as e:
        print("floodfill err", c, e)

rgba = im.convert("RGBA")
px = rgba.load()
count = 0
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if (r, g, b) == MARKER:
            px[x, y] = (0, 0, 0, 0)
            count += 1
rgba.save(OUT)
print(f"done: {count} px transparent, size={rgba.size}")
