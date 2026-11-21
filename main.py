#!/usr/bin/env python3
"""RAINBREW 3000 - catalogue photo of an impossible gadget.

Studio product shot, drawn procedurally with the standard library only:
a small cloud rains into the steel funnel of an espresso machine, which
pulls a shot into a cup on its drip tray. Deterministic: two runs of
this program produce byte-identical PNG files. Output: 1024x1024 PNG
at /output/entry.png (override with the OUTPUT_PATH environment variable).
"""
import math
import os
import struct
import zlib

S = 2                    # supersample factor for anti-aliasing
W = H = 1024             # final image size
DW = W * S               # device (drawing) size
buf = bytearray(DW * DW * 3)


def put(dx, dy, col, a=1.0):
    if 0 <= dx < DW and 0 <= dy < DW:
        i = (dy * DW + dx) * 3
        if a >= 1.0:
            buf[i] = col[0]
            buf[i + 1] = col[1]
            buf[i + 2] = col[2]
        else:
            buf[i] = int(buf[i] * (1 - a) + col[0] * a)
            buf[i + 1] = int(buf[i + 1] * (1 - a) + col[1] * a)
            buf[i + 2] = int(buf[i + 2] * (1 - a) + col[2] * a)


def rect(x0, y0, x1, y1, col, a=1.0):
    X0, Y0, X1, Y1 = int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S)
    if a >= 1.0:
        row = bytes(col) * (X1 - X0)
        for dy in range(Y0, Y1):
            i = (dy * DW + X0) * 3
            buf[i:i + len(row)] = row
    else:
        for dy in range(Y0, Y1):
            for dx in range(X0, X1):
                put(dx, dy, col, a)


def ellipse(cx, cy, rx, ry, col, a=1.0):
    CX, CY, RX, RY = cx * S, cy * S, rx * S, ry * S
    for dy in range(int(CY - RY), int(CY + RY) + 1):
        t = (dy - CY) / RY
        if -1.0 <= t <= 1.0:
            span = RX * math.sqrt(1.0 - t * t)
            x0, x1 = int(CX - span), int(CX + span)
            if a >= 1.0:
                row = bytes(col) * (x1 - x0)
                i = (dy * DW + x0) * 3
                buf[i:i + len(row)] = row
            else:
                for dx in range(x0, x1):
                    put(dx, dy, col, a)


def disc(cx, cy, r, col, a=1.0):
    ellipse(cx, cy, r, r, col, a)


def rrect(x0, y0, x1, y1, r, col, a=1.0):
    X0, Y0, X1, Y1, R = int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S), int(r * S)
    for dy in range(Y0, Y1):
        inset = 0
        if dy < Y0 + R:
            d = (Y0 + R) - dy
            inset = int(R - math.sqrt(max(0, R * R - d * d)))
        elif dy >= Y1 - R:
            d = dy - (Y1 - R) + 1
            inset = int(R - math.sqrt(max(0, R * R - d * d)))
        xa, xb = X0 + inset, X1 - inset
        if a >= 1.0:
            row = bytes(col) * (xb - xa)
            i = (dy * DW + xa) * 3
            buf[i:i + len(row)] = row
        else:
            for dx in range(xa, xb):
                put(dx, dy, col, a)


def line(x0, y0, x1, y1, col, w=2.0, a=1.0):
    steps = int(max(abs(x1 - x0), abs(y1 - y0)) * S) + 1
    for k in range(steps + 1):
        t = k / steps
        disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, w / 2, col, a)


def poly(points, col, a=1.0):
    ys = [p[1] for p in points]
    for y in range(int(min(ys) * S), int(max(ys) * S)):
        yc = (y + 0.5) / S
        xs = []
        n = len(points)
        for i in range(n):
            xa, ya = points[i]
            xb, yb = points[(i + 1) % n]
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            rect(xs[i], yc - 0.25, xs[i + 1], yc + 0.25, col, a)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


FONT = {
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def draw_text(text, cx, y, scale, col):
    adv = 6 * scale
    total = len(text) * adv - scale
    x = cx - total // 2
    for ch in text:
        glyph = FONT[ch]
        for gy in range(7):
            for gx in range(5):
                if glyph[gy][gx] == "1":
                    rect(x + gx * scale, y + gy * scale,
                         x + gx * scale + scale, y + gy * scale + scale, col)
        x += adv


# ---------- background: clean studio sweep ----------
for dy in range(DW):
    yd = dy / S
    if yd < 798:
        col = lerp((240, 242, 245), (216, 220, 226), yd / 798)
    else:
        col = lerp((203, 208, 215), (188, 194, 202), (yd - 798) / 226)
    row = bytes(col) * DW
    i = dy * DW * 3
    buf[i:i + len(row)] = row

# soft floor shadow under the machine
ellipse(512, 828, 318, 27, (28, 30, 34), 0.32)

# ---------- the little rain cloud ----------
ellipse(512, 142, 160, 49, (202, 210, 219))          # shaded underside
ellipse(512, 124, 152, 46, (249, 250, 251))          # main puff
ellipse(424, 106, 58, 36, (249, 250, 251))
ellipse(602, 104, 64, 40, (249, 250, 251))
ellipse(512, 96, 72, 42, (252, 252, 253))

# ---------- rain: deterministic streaks falling into the funnel ----------
state = 987654321


def rnd(mod):
    global state
    state = (1103515245 * state + 12345) % 2147483648
    return state % mod


for _ in range(52):
    x = 408 + rnd(208)
    y = 182 + rnd(96)
    ln = 24 + rnd(20)
    line(x, y, x - 5, y + ln, (104, 160, 222), 2.6, 0.8)

for sx in (438, 479, 521, 563, 598):
    ellipse(sx, 299, 8, 2.4, (168, 198, 233), 0.75)

# ---------- funnel on top of the machine ----------
poly([(388, 304), (636, 304), (552, 394), (472, 394)], (126, 136, 148))
poly([(388, 304), (472, 304), (494, 394), (472, 394)], (104, 114, 126))
ellipse(512, 304, 126, 17, (72, 78, 86))              # rim
ellipse(512, 304, 107, 13, (28, 32, 38))              # dark opening
rect(474, 316, 550, 384, (108, 117, 128))             # neck
rect(474, 316, 497, 384, (90, 98, 108))
rect(474, 342, 550, 351, (148, 157, 168))
rect(474, 342, 497, 351, (124, 133, 144))

# ---------- machine body: brushed steel, horizontal gradient ----------
BX0, BX1, BY0, BY1, BR = 330, 694, 378, 772, 38
stops = [(0.0, (102, 110, 120)), (0.28, (170, 178, 188)),
         (0.5, (201, 209, 219)), (0.78, (156, 164, 174)),
         (1.0, (96, 104, 114))]


def grad(stops, t):
    for i in range(len(stops) - 1):
        if stops[i][0] <= t <= stops[i + 1][0]:
            f = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0])
            return lerp(stops[i][1], stops[i + 1][1], f)
    return stops[-1][1]


pattern = b"".join(bytes(grad(stops, dx / (DW - 1))) for dx in range(DW))
X0, X1, Y0, Y1, R = BX0 * S, BX1 * S, BY0 * S, BY1 * S, BR * S
for dy in range(Y0, Y1):
    inset = 0
    if dy < Y0 + R:
        d = (Y0 + R) - dy
        inset = int(R - math.sqrt(max(0, R * R - d * d)))
    elif dy >= Y1 - R:
        d = dy - (Y1 - R) + 1
        inset = int(R - math.sqrt(max(0, R * R - d * d)))
    xa, xb = X0 + inset, X1 - inset
    i = (dy * DW + xa) * 3
    buf[i:i + (xb - xa) * 3] = pattern[xa * 3:xb * 3]
rrect(BX0, BY0, BX1, BY0 + 26, 18, (214, 221, 228), 0.5)   # top sheen

# ---------- brand plate and lettering (text belongs to the product) ----------
rrect(386, 422, 638, 490, 12, (35, 37, 41))
draw_text("RAINBREW", 512, 439, 5, (232, 235, 238))
draw_text("MODEL 3000", 512, 500, 2, (72, 77, 84))

# ---------- control panel: gauge, buttons, knob ----------
rrect(356, 522, 668, 650, 18, (122, 130, 140))
rrect(363, 529, 661, 643, 14, (134, 143, 153))
disc(410, 586, 37, (38, 40, 44))
disc(410, 586, 32, (198, 203, 210))
disc(410, 586, 28, (244, 245, 246))
for k in range(9):
    ang = math.radians(-225 + k * 33)
    line(410 + 21 * math.cos(ang), 586 + 21 * math.sin(ang),
         410 + 26 * math.cos(ang), 586 + 26 * math.sin(ang),
         (196, 60, 50) if k >= 6 else (52, 55, 60), 2.2)
line(410, 586, 410 + 20 * math.cos(math.radians(-48)),
     586 + 20 * math.sin(math.radians(-48)), (178, 44, 40), 3.2)
disc(410, 586, 4, (38, 40, 44))
disc(492, 586, 10, (50, 53, 58))
disc(492, 586, 4, (196, 70, 58))
disc(540, 586, 10, (50, 53, 58))
disc(540, 586, 4, (74, 168, 96))
disc(618, 586, 27, (42, 45, 50))
disc(618, 586, 21, (58, 62, 68))
line(618, 586, 618, 569, (210, 215, 220), 3.4)

# corner screws
for sx, sy in ((356, 404), (668, 404), (356, 746), (668, 746)):
    disc(sx, sy, 5, (58, 62, 68))
    disc(sx - 1, sy - 1, 2, (168, 175, 183))

# ---------- group head, portafilter, spouts ----------
rect(444, 650, 580, 688, (56, 60, 66))
rect(444, 680, 580, 691, (42, 45, 50))
rect(464, 691, 560, 705, (84, 90, 98))
line(492, 705, 498, 719, (42, 45, 50), 3.4)
line(532, 705, 526, 719, (42, 45, 50), 3.4)
line(570, 668, 702, 701, (25, 24, 26), 15)            # portafilter handle
disc(706, 702, 11, (25, 24, 26))
line(578, 659, 696, 690, (120, 124, 130), 3, 0.5)     # handle highlight

# ---------- feet and drip tray ----------
rect(374, 768, 414, 798, (44, 47, 52))
rect(610, 768, 650, 798, (44, 47, 52))
rrect(358, 794, 666, 822, 8, (52, 56, 62))
for k in range(6):
    rect(396 + k * 40, 801, 399 + k * 40, 815, (92, 98, 106))

ellipse(512, 801, 64, 6, (18, 20, 24), 0.3)

# ---------- the cup (the one accessory story: the shot being pulled) ----------
poly([(460, 742), (564, 742), (548, 798), (476, 798)], (246, 247, 248))
poly([(524, 742), (564, 742), (548, 798), (520, 798)], (223, 227, 233))
for k in range(15):                                    # cup handle
    ang = math.radians(-72 + k * 10)
    disc(562 + 17 * math.cos(ang), 770 + 17 * math.sin(ang), 4.6, (233, 236, 239))
ellipse(512, 743, 51, 9, (99, 59, 29))                 # coffee surface
ellipse(498, 742, 20, 4, (130, 85, 46))                # crema swirl
line(512, 717, 512, 741, (101, 63, 33), 3.6)           # the stream

# steam wisps rising off the shot
for cx, ph in ((490, 0.0), (512, 4.2), (534, 2.1)):
    for t in range(88):
        y = 738 - t * 0.62
        x = cx + 9 * math.sin(t * 0.11 + ph)
        disc(x, y, 1.9, (238, 240, 242), 0.4)


# ---------- downscale 2x and write the PNG ----------
out = bytearray(W * H * 3)
for oy in range(H):
    for ox in range(W):
        i0 = ((2 * oy) * DW + 2 * ox) * 3
        i1 = i0 + 3
        i2 = i0 + DW * 3
        i3 = i2 + 3
        o = (oy * W + ox) * 3
        for c in range(3):
            out[o + c] = (buf[i0 + c] + buf[i1 + c] + buf[i2 + c] + buf[i3 + c]) // 4

raw = b"".join(b"\x00" + bytes(out[y * W * 3:(y + 1) * W * 3]) for y in range(H))


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))

path = os.environ.get("OUTPUT_PATH", "/output/entry.png")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "wb") as f:
    f.write(png)
print("wrote", path, len(png), "bytes")
