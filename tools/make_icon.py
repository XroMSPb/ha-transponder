"""Generate the project icon (original artwork, not the ЗСД trademark).

Concept: a blue app-badge with a white transponder device showing the ruble
sign, transmitting signal arcs upward (toll gantry / balance refresh).

Outputs (icons/):
    icon.png       256x256   (Home Assistant brands "icon")
    icon@2x.png    512x512   (brands "icon@2x")
    logo.png       512x512   (square logo for README / HACS)

Run:  python tools/make_icon.py
Requires: Pillow
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons"
)

# Render at 4x the largest target for crisp downscaling.
S = 1024

TOP = (36, 128, 214)      # #2480D6
BOTTOM = (10, 52, 122)    # #0A347A
DEVICE = (255, 255, 255)
INK = (11, 60, 130)       # ruble glyph color


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    """A bold font that contains the ruble sign (U+20BD)."""
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\seguisb.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient_square(size: int) -> Image.Image:
    """Vertical blue gradient."""
    grad = Image.new("RGB", (size, size), TOP)
    px = grad.load()
    for y in range(size):
        t = y / (size - 1)
        r = round(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = round(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = round(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return grad


def build_master() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Rounded-square badge with gradient fill.
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255
    )
    img.paste(_gradient_square(S), (0, 0), mask)

    draw = ImageDraw.Draw(img)

    # Signal arcs transmitting upward from the top of the device.
    cx, cy = S // 2, int(S * 0.40)
    for i, radius in enumerate((150, 230, 310)):
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        draw.arc(bbox, start=205, end=335, fill=(255, 255, 255, 235), width=34)
    # Emitter dot.
    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(255, 255, 255, 255))

    # Transponder device: white rounded rectangle with a soft shadow.
    dev_w, dev_h = int(S * 0.56), int(S * 0.36)
    dev_cx, dev_cy = S // 2, int(S * 0.60)
    left = dev_cx - dev_w // 2
    top = dev_cy - dev_h // 2
    box = [left, top, left + dev_w, top + dev_h]
    shadow = [box[0] + 14, box[1] + 20, box[2] + 14, box[3] + 20]
    draw.rounded_rectangle(shadow, radius=70, fill=(4, 20, 50, 90))
    draw.rounded_rectangle(box, radius=70, fill=DEVICE)

    # Ruble sign centered on the device.
    font = _find_font(int(dev_h * 0.78))
    glyph = "\u20bd"  # ₽
    tb = draw.textbbox((0, 0), glyph, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text(
        (dev_cx - tw / 2 - tb[0], dev_cy - th / 2 - tb[1]),
        glyph,
        font=font,
        fill=INK,
    )
    return img


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    master = build_master()
    master.resize((512, 512), Image.LANCZOS).save(
        os.path.join(OUT_DIR, "icon@2x.png")
    )
    master.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT_DIR, "logo.png"))
    master.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT_DIR, "icon.png"))
    print("Wrote icons to", OUT_DIR)


if __name__ == "__main__":
    main()
