"""The phone bezel (its screen cut out), the touch ring and the end card's icon, for compose.mjs.
Usage: python3 bezel.py <out dir> <icon png>. Needs Pillow."""
import sys

from PIL import Image, ImageDraw, ImageFilter

out, icon = sys.argv[1], sys.argv[2]
W, H = 1080, 1920
# The film is 1206x2622 (402x874 points): 684 wide makes it 1488 high.
SCREEN = (198, 350, 882, 1838)
BODY = (178, 330, 902, 1858)

hole = Image.new("L", (W, H), 0)
ImageDraw.Draw(hole).rounded_rectangle(SCREEN, radius=86, fill=255)
clear = Image.new("L", (W, H), 0)

shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((BODY[0], BODY[1] + 20, BODY[2], BODY[3] + 20), radius=104, fill=(31, 36, 48, 70))
shadow = shadow.filter(ImageFilter.GaussianBlur(30))
body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(body)
draw.rounded_rectangle(BODY, radius=104, fill=(14, 12, 10, 255))
draw.rounded_rectangle((BODY[0] + 2, BODY[1] + 2, BODY[2] - 2, BODY[3] - 2), radius=102, outline=(60, 64, 76, 255), width=3)
for layer in (body, shadow):
    layer.putalpha(Image.composite(clear, layer.getchannel("A"), hole))
Image.alpha_composite(shadow, body).save(f"{out}/bezel.png")

tap = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
# The landing page's indigo, which reads on the app's white lists and its blue accents alike.
ImageDraw.Draw(tap).ellipse((6, 6, 84, 84), fill=(67, 56, 202, 80), outline=(67, 56, 202, 255), width=5)
tap.save(f"{out}/tap.png")
Image.open(icon).convert("RGBA").resize((300, 300), Image.LANCZOS).save(f"{out}/icon.png")
