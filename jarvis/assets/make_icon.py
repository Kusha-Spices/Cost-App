"""Generate the Jarvis app icon — a golden filament 'orb' on a dark background.

Pure standard library (no Pillow). Run:  python assets/make_icon.py
Produces assets/icon.png. build_app.sh converts it to icon.icns for the .app.

To use your OWN image instead, just overwrite assets/icon.png with it.
"""
from __future__ import annotations

import math
import os
import random
import struct
import zlib

W = H = 512
CX = CY = W / 2.0
RMAX = W / 2.0
PAD = 30
CORNER = 116

GOLD = (255, 165, 35)
GOLD_HI = (255, 214, 120)
WHITE = (255, 246, 214)
BG_IN = (18, 24, 38)
BG_OUT = (5, 8, 14)

rgb = [0] * (W * H * 3)
alpha = bytearray(W * H)


def _add(x: int, y: int, col, k: float) -> None:
    if k <= 0 or x < 0 or y < 0 or x >= W or y >= H:
        return
    i = (y * W + x) * 3
    rgb[i] = min(255, rgb[i] + int(col[0] * k))
    rgb[i + 1] = min(255, rgb[i + 1] + int(col[1] * k))
    rgb[i + 2] = min(255, rgb[i + 2] + int(col[2] * k))


def _glow(xf: float, yf: float, col, k: float) -> None:
    x, y = int(round(xf)), int(round(yf))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            w = 1.0 if (dx or dy) == 0 else (0.35 if dx == 0 or dy == 0 else 0.16)
            _add(x + dx, y + dy, col, k * w)


def _background() -> None:
    half = (W - 2 * PAD) / 2
    for y in range(H):
        for x in range(W):
            qx = abs(x - CX) - (half - CORNER)
            qy = abs(y - CY) - (half - CORNER)
            d = min(max(qx, qy), 0.0) + math.hypot(max(qx, 0.0), max(qy, 0.0)) - CORNER
            if d >= 1:
                continue
            alpha[y * W + x] = 255 if d <= -1 else int((1 - (d + 1) / 2) * 255)
            t = min(math.hypot(x - CX, y - CY) / RMAX, 1.0)
            i = (y * W + x) * 3
            rgb[i] = int(BG_IN[0] + (BG_OUT[0] - BG_IN[0]) * t)
            rgb[i + 1] = int(BG_IN[1] + (BG_OUT[1] - BG_IN[1]) * t)
            rgb[i + 2] = int(BG_IN[2] + (BG_OUT[2] - BG_IN[2]) * t)


def _filaments() -> None:
    random.seed(11)
    for _ in range(170):
        ang = random.uniform(0, 2 * math.pi)
        ca, sa = math.cos(ang), math.sin(ang)
        inner = random.uniform(0.05, 0.12) * RMAX
        outer = random.uniform(0.40, 0.95) * RMAX
        base = random.uniform(0.30, 1.0)
        n = max(1, int(outer - inner))
        for s in range(n):
            rr = inner + s
            t = s / n
            b = base * (0.35 + 0.65 * math.sin(t * math.pi)) * (0.6 + 0.4 * random.random())
            _glow(CX + rr * ca, CY + rr * sa, GOLD if b < 0.7 else GOLD_HI, b * 0.9)
        if random.random() < 0.55:
            rr = outer * random.uniform(0.7, 1.0)
            _glow(CX + rr * ca, CY + rr * sa, WHITE, 1.0)


def _rings() -> None:
    # bright orbiting arcs
    for radius, a0, a1, bright in (
        (0.52, 0.6, 4.4, 1.0),
        (0.40, 3.2, 6.0, 0.85),
        (0.63, 4.7, 7.6, 0.7),
    ):
        r = radius * RMAX
        a = a0
        while a < a1:
            _glow(CX + r * math.cos(a), CY + r * math.sin(a), GOLD_HI, bright)
            a += 0.35 / r
    # faint full shell
    r = 0.92 * RMAX
    a = 0.0
    while a < 2 * math.pi:
        _glow(CX + r * math.cos(a), CY + r * math.sin(a), GOLD, 0.25 + 0.25 * random.random())
        a += 0.6 / r


def _sparkle() -> None:
    random.seed(29)
    for _ in range(520):
        rr = random.uniform(0.1, 0.9) * RMAX
        ang = random.uniform(0, 2 * math.pi)
        _add(int(CX + rr * math.cos(ang)), int(CY + rr * math.sin(ang)),
             GOLD_HI, random.uniform(0.2, 0.9))


def _core() -> None:
    rad = 0.2 * RMAX
    for y in range(int(CY - rad), int(CY + rad)):
        for x in range(int(CX - rad), int(CX + rad)):
            t = math.hypot(x - CX, y - CY) / rad
            if t < 1:
                _glow(x, y, WHITE, (1 - t) ** 2 * 0.9)


def write_png(path: str) -> None:
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        for x in range(W):
            i = (y * W + x) * 3
            raw += bytes((rgb[i], rgb[i + 1], rgb[i + 2], alpha[y * W + x]))

    def chunk(typ, data):
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    _background()
    _filaments()
    _rings()
    _sparkle()
    _core()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    write_png(out)
    print("wrote", out)
