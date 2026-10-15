import sys, os
from PIL import Image, ImageDraw
src, dst = sys.argv[1], sys.argv[2]
W, H, M = 1080, 1920, 70
bg = (0x4B, 0x58, 0x8B)
for f in sorted(os.listdir(src)):
    if not f[:2].isdigit() or f.startswith("00"): continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    h = H - 2 * M
    w = round(im.width * h / im.height)
    im = im.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=44, fill=255)
    canvas = Image.new("RGB", (W, H), bg)
    canvas.paste(im, ((W - w) // 2, M), mask)
    canvas.save(os.path.join(dst, f), optimize=True)
    print(f, canvas.size)
