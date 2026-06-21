#!/usr/bin/env python3
"""Generate build/icon.png — an aurora-borealis app icon — with zero deps.
Writes a 1024x1024 RGBA PNG (rounded-square, dark sky, aurora ribbons, stars)."""
import math, os, struct, zlib, random

W = H = 1024
RAD = 200          # corner radius for the rounded square
random.seed(11)


def clampi(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


# Aurora ribbons: (base vertical position 0..1, RGB colour, half-width, amplitude)
BANDS = [
    (0.34, (124, 92, 255), 0.17, 0.060),   # violet
    (0.46, (45, 212, 255), 0.15, 0.050),   # cyan
    (0.58, (84, 230, 165), 0.18, 0.070),   # green
    (0.50, (255, 92, 240), 0.13, 0.045),   # magenta
]

# Precompute per-column wave centre + streak so the inner loop stays cheap.
wave = [[0.0] * len(BANDS) for _ in range(W)]
streak = [[0.0] * len(BANDS) for _ in range(W)]
for x in range(W):
    tx = x / W
    for bi, (cy, _c, _hw, amp) in enumerate(BANDS):
        wave[x][bi] = cy + amp * math.sin(tx * math.pi * 3.0 + cy * 9) + amp * 0.6 * math.sin(tx * math.pi * 6 + bi)
        streak[x][bi] = 0.55 + 0.45 * math.sin(tx * math.pi * 9 + bi * 5)

data = bytearray(W * H * 4)

for y in range(H):
    ty = y / H
    bg_r = 9 + ty * 14
    bg_g = 10 + ty * 18
    bg_b = 26 + ty * 40
    dy = ty - 0.5
    row = y * W * 4
    for x in range(W):
        r, g, b = bg_r, bg_g, bg_b
        wv = wave[x]
        sk = streak[x]
        for bi, (cy, col, hw, amp) in enumerate(BANDS):
            d = ty - wv[bi]
            if d < 0:
                d = -d
            if d < hw:
                inten = (1.0 - d / hw)
                inten = inten * inten * sk[bi]
                r += col[0] * inten
                g += col[1] * inten
                b += col[2] * inten
        # vignette (no sqrt: use squared radius)
        dx = x / W - 0.5
        vd2 = dx * dx + dy * dy
        vig = 1.0 - vd2 * 1.15
        if vig < 0.45:
            vig = 0.45
        r *= vig; g *= vig; b *= vig

        # rounded-square alpha mask (anti-aliased corners)
        a = 255
        cx = RAD if x < RAD else (W - 1 - RAD if x > W - 1 - RAD else x)
        cyy = RAD if y < RAD else (H - 1 - RAD if y > H - 1 - RAD else y)
        ddx = x - cx; ddy = y - cyy
        if ddx or ddy:
            dist = math.sqrt(ddx * ddx + ddy * ddy)
            if dist > RAD:
                a = 0
            elif dist > RAD - 1.5:
                a = clampi((RAD - dist) / 1.5 * 255)

        i = row + x * 4
        data[i] = clampi(r); data[i + 1] = clampi(g); data[i + 2] = clampi(b); data[i + 3] = a

# stars (small soft points in the upper sky)
for _ in range(70):
    sx = random.randint(40, W - 40)
    sy = random.randint(40, int(H * 0.5))
    bright = random.uniform(0.5, 1.0)
    for ox, oy, f in ((0, 0, 1.0), (1, 0, 0.4), (-1, 0, 0.4), (0, 1, 0.4), (0, -1, 0.4)):
        px, py = sx + ox, sy + oy
        i = (py * W + px) * 4
        v = int(255 * bright * f)
        data[i] = min(255, data[i] + v)
        data[i + 1] = min(255, data[i + 1] + v)
        data[i + 2] = min(255, data[i + 2] + v)


def write_png(path, w, h, rgba):
    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    stride = w * 4
    raw = bytearray()
    for yy in range(h):
        raw.append(0)  # no filter
        raw += rgba[yy * stride:(yy + 1) * stride]
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
write_png(out, W, H, data)
print("wrote", out, "(%dx%d)" % (W, H))
