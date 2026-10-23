"""Draw the link-preview image (og.png, 1200x630) in the site's night-shinobi style.

    python3 tools/make_og.py og.png

Everything is procedural: value-noise mist, geometric seals, rooftop silhouettes,
embers and grain. No outside images or franchise symbols. Needs Pillow and numpy.
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
S = 2
W, H = 1200 * S, 630 * S
rng = np.random.default_rng(7)
random.seed(7)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size * S))


def value_noise(w, h, octaves=6, base=3):
    """Smooth fractal noise in 0..1 built from upsampled random grids."""
    acc = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = base * (2 ** o)
        grid = rng.random((cells + 1, int(cells * w / h) + 2)).astype(np.float32)
        layer = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += np.asarray(layer, np.float32) / 255.0 * amp
        total += amp
        amp *= 0.5
    acc /= total
    return (acc - acc.min()) / (acc.max() - acc.min())


def radial(w, h, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return np.clip(1 - d, 0, 1)


def add_color(base, mask, color, strength):
    m = (mask * strength)[..., None]
    col = np.array(color, np.float32)[None, None, :]
    return base * (1 - m) + col * m


def bez(p0, p1, p2, n=14):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def roof_polys(cx, y, w, h):
    L, R, f = cx - w / 2, cx + w / 2, w * 0.16
    eave = bez((L, y), (L + f * 0.55, y - 3), (L + f, y - 8)) + bez((R - f, y - 8), (R - f * 0.55, y - 3), (R, y)) + [(R - f * 0.35, y + 4), (L + f * 0.35, y + 4)]
    top = [(L + f, y - 8), (cx - w * 0.17, y - h), (cx + w * 0.17, y - h), (R - f, y - 8)]
    rim = bez((L, y), (L + f * 0.55, y - 3), (L + f, y - 8)) + bez((R - f, y - 8), (R - f * 0.55, y - 3), (R, y))
    return eave, top, rim


def skyline(scale, ox, oy, mirror=False):
    """Pagoda + low houses, in a 600x270 box scaled and placed at (ox, oy) = bottom-left of the box."""
    polys, rims = [], []
    def T(pts):
        out = []
        for x, y in pts:
            if mirror:
                x = 600 - x
            out.append((ox + x * scale, oy - (270 - y) * scale))
        return out
    cx, base, y, prev = 118, 262, 236, 262
    for w in [168, 140, 114, 90, 68]:
        e, t, r = roof_polys(cx, y, w, 16)
        polys += [T(e), T(t), T([(cx - w * 0.33, y + 4), (cx + w * 0.33, y + 4), (cx + w * 0.33, prev), (cx - w * 0.33, prev)])]
        rims.append(T(r))
        prev, y = y - 6, y - 40
    top_y = y + 40 - 16
    polys.append(T([(cx - 2, top_y - 46), (cx + 2, top_y - 46), (cx + 2, top_y), (cx - 2, top_y)]))
    for (hx, hw, hh) in [(262, 110, 58), (360, 96, 44), (450, 120, 64), (548, 90, 40)]:
        ry = base - hh
        e, t, r = roof_polys(hx, ry, hw, 18)
        polys += [T(e), T(t), T([(hx - hw * 0.38, ry + 4), (hx + hw * 0.38, ry + 4), (hx + hw * 0.38, base), (hx - hw * 0.38, base)])]
        rims.append(T(r))
    polys.append(T([(-10, base), (620, base), (620, 280), (-10, 280)]))
    return polys, rims


def seal(img, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = color + (alpha,)
    def ring(rr, width=1):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=c, width=max(1, int(width * S)))
    ring(r, 1.4); ring(r * 0.75, 1.2); ring(r * 0.39, 1); ring(r * 0.22, 1.4)
    for i in range(96):  # dotted ring
        a = i / 96 * 2 * math.pi
        x, y = cx + math.cos(a) * r * 0.945, cy + math.sin(a) * r * 0.945
        d.ellipse([x - S, y - S, x + S, y + S], fill=c)
    for i in range(24):  # ticks
        a = i / 24 * 2 * math.pi
        d.line([(cx + math.cos(a) * r * 0.80, cy + math.sin(a) * r * 0.80), (cx + math.cos(a) * r * 0.86, cy + math.sin(a) * r * 0.86)], fill=c, width=2 * S)
    for k in range(4):  # broken arc ring
        start = k * 90 + 8
        d.arc([cx - r * 0.65, cy - r * 0.65, cx + r * 0.65, cy + r * 0.65], start, start + 62, fill=c, width=3 * S)
    for rot in (0, 45):  # crossed squares
        pts = []
        for i in range(4):
            a = math.radians(rot + 45 + i * 90)
            pts.append((cx + math.cos(a) * r * 0.56, cy + math.sin(a) * r * 0.56))
        d.polygon(pts, outline=c, width=max(1, S))
    for a in (0, 90, 180, 270):
        x, y = cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r
        d.ellipse([x - 4 * S, y - 4 * S, x + 4 * S, y + 4 * S], fill=c)
    glow = layer.filter(ImageFilter.GaussianBlur(6 * S))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def stream(img, pts, c0, c1, width):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    n = len(pts) - 1
    for i in range(n):
        t = i / n
        a = int(255 * math.sin(math.pi * t) ** 1.5)
        col = tuple(int(c0[j] + (c1[j] - c0[j]) * t) for j in range(3)) + (a,)
        d.line([pts[i], pts[i + 1]], fill=col, width=int(width * S))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(5 * S)))
    img.alpha_composite(layer)


def cubic(p0, p1, p2, p3, n=80):
    return [(((1 - t) ** 3) * p0[0] + 3 * ((1 - t) ** 2) * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             ((1 - t) ** 3) * p0[1] + 3 * ((1 - t) ** 2) * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]) for t in [i / n for i in range(n + 1)]]


def spaced_center(d, y, text, f, fill, tracking):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill)
        x += w + tracking


def skew_panel(img, x0, y0, x1, y1, c0, c1, glow_col):
    off = (y1 - y0) * math.tan(math.radians(10))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(x0 + off, y0), (x1 + off, y0), (x1, y1), (x0, y1)], fill=glow_col + (150,))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24 * S)))
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(int(x0), int(x1 + off) + 1):
        t = (x - x0) / max(1, (x1 + off - x0))
        gd.line([(x, y0), (x, y1)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon([(x0 + off, y0), (x1 + off, y0), (x1, y1), (x0, y1)], fill=255)
    img.paste(grad, (0, 0), mask)
    return off


def main(out):
    # --- base gradient and coloured mist (numpy) ---
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    top, mid, bot = np.array([12, 10, 24], np.float32), np.array([7, 7, 13], np.float32), np.array([8, 7, 15], np.float32)
    base = np.where(yy[..., None] < 0.45, top + (mid - top) * (yy[..., None] / 0.45), mid + (bot - mid) * ((yy[..., None] - 0.45) / 0.55))
    base = np.broadcast_to(base, (H, W, 3)).copy()
    base = add_color(base, radial(W, H, 0, H, W * 0.75, H * 1.1), (40, 26, 92), 0.6)
    base = add_color(base, radial(W, H, W, H, W * 0.7, H * 1.0), (120, 30, 18), 0.45)
    n1, n2 = value_noise(W, H, 6, 2), value_noise(W, H, 6, 3)
    violet = np.clip((n1 - 0.38) * 2.2, 0, 1) * radial(W, H, -W * 0.02, H * 0.42, W * 0.42, H * 0.95)
    ember = np.clip((n2 - 0.4) * 2.2, 0, 1) * radial(W, H, W * 1.02, H * 0.55, W * 0.4, H * 0.95)
    base = add_color(base, violet, (115, 78, 240), 0.75)
    base = add_color(base, ember, (255, 92, 34), 0.55)
    # top glow behind the title
    base = add_color(base, radial(W, H, W * 0.5, 0, W * 0.5, H * 0.75), (110, 80, 230), 0.32)
    base = add_color(base, radial(W, H, W * 0.5, H * 0.22, W * 0.25, H * 0.32), (255, 128, 60), 0.14)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")

    # --- seals, streams ---
    seal(img, int(-40 * S), int(250 * S), int(250 * S), (160, 130, 255), 70)
    seal(img, int(1250 * S), int(420 * S), int(240 * S), (255, 150, 70), 62)
    stream(img, cubic((40 * S, 640 * S), (110 * S, 470 * S), (20 * S, 330 * S), (130 * S, -10 * S)), (156, 123, 255), (91, 63, 214), 1.6)
    stream(img, cubic((1170 * S, 640 * S), (1090 * S, 460 * S), (1185 * S, 300 * S), (1075 * S, -10 * S)), (255, 176, 102), (255, 74, 42), 1.6)

    # --- calm centre for the text ---
    calm = np.zeros((H, W), np.float32)
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    calm = np.clip(1 - np.abs(xx - 0.5) / 0.36, 0, 1) ** 0.8 * 0.55
    dark = Image.fromarray((np.broadcast_to(calm, (H, W)) * 255).astype(np.uint8))
    shade = Image.new("RGBA", img.size, (6, 6, 11, 255))
    img = Image.composite(shade, img, dark)

    # --- rooftops in the corners ---
    sil = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sil)
    for mirror, rim_col in ((False, (150, 120, 255, 140)), (True, (255, 140, 80, 120))):
        sc = 0.62 * S
        ox = 0 if not mirror else W - 600 * sc
        polys, rims = skyline(sc, ox, H, mirror)
        for p in polys:
            sd.polygon(p, fill=(5, 5, 11, 255))
        for r in rims:
            sd.line(r, fill=rim_col, width=max(1, int(1.2 * S)))
    img.alpha_composite(sil)

    # --- embers ---
    emb = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ed = ImageDraw.Draw(emb)
    for _ in range(46):
        side = random.random() < 0.5
        x = random.uniform(10, 230) if side else random.uniform(970, 1190)
        y = random.uniform(40, 600)
        rr = random.choice([1.2, 1.5, 2, 2.4])
        a = random.randint(110, 230)
        ed.ellipse([(x - rr) * S, (y - rr) * S, (x + rr) * S, (y + rr) * S], fill=(255, 178, 107, a))
    img.alpha_composite(emb.filter(ImageFilter.GaussianBlur(3 * S)))
    img.alpha_composite(emb)

    # --- grain ---
    g = (rng.random((H // 2, W // 2)) * 255).astype(np.uint8)
    grain = Image.fromarray(g).resize((W, H), Image.NEAREST).convert("L")
    gl = Image.new("RGBA", img.size, (255, 255, 255, 0))
    gl.putalpha(grain.point(lambda v: int(v * 0.05)))
    img.alpha_composite(gl)

    # --- typography ---
    d = ImageDraw.Draw(img)
    eyebrow = font("Exo2-SemiBold.ttf", 23)
    title = font("RussoOne.ttf", 168)
    panel_f = font("RussoOne.ttf", 46)
    vs_f = font("RussoOne.ttf", 34)
    foot = font("Exo2-SemiBold.ttf", 22)
    url_f = font("Exo2-SemiBold.ttf", 24)

    spaced_center(d, 52 * S, "NARUTO LEGEND 3.0 · РЕЙТИНГОВЫЙ СЕЗОН", eyebrow, (170, 162, 200), 5 * S)
    tw = d.textlength("IMMORTAL", font=title)
    tx, ty = (W - tw) / 2, 84 * S
    tl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(tl).text((tx, ty), "IMMORTAL", font=title, fill=(170, 140, 255, 150))
    img.alpha_composite(tl.filter(ImageFilter.GaussianBlur(22 * S)))
    tl2 = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(tl2).text((tx, ty), "IMMORTAL", font=title, fill=(255, 140, 70, 70))
    img.alpha_composite(tl2.filter(ImageFilter.GaussianBlur(40 * S)))
    d = ImageDraw.Draw(img)
    d.text((tx, ty), "IMMORTAL", font=title, fill=(244, 242, 250))

    y0, y1 = 318 * S, 410 * S
    off = skew_panel(img, 214 * S, y0, 566 * S, y1, (19, 94, 168), (47, 155, 255), (47, 155, 255))
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), "АЛЬЯНС", font=panel_f)
    d.text((214 * S + off / 2 + 30 * S, y0 + (y1 - y0 - (bb[3] - bb[1])) / 2 - bb[1]), "АЛЬЯНС", font=panel_f, fill=(255, 255, 255))
    off2 = skew_panel(img, 634 * S - off, y0, 986 * S - off, y1, (255, 58, 92), (158, 22, 48), (255, 58, 92))
    d = ImageDraw.Draw(img)
    lab = "АКАЦУКИ"
    lw = d.textlength(lab, font=panel_f)
    d.text((986 * S - off + off2 / 2 - 30 * S - lw, y0 + (y1 - y0 - (bb[3] - bb[1])) / 2 - bb[1]), lab, font=panel_f, fill=(255, 255, 255))
    vw = d.textlength("VS", font=vs_f)
    vb = d.textbbox((0, 0), "VS", font=vs_f)
    d.text((600 * S - vw / 2 + off / 2 - 6 * S, y0 + (y1 - y0 - (vb[3] - vb[1])) / 2 - vb[1]), "VS", font=vs_f, fill=(170, 162, 200))

    # ornament divider
    oy = 468 * S
    orn = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(orn)
    for i in range(0, 260 * S):
        a = int(150 * (i / (260 * S)))
        od.point((600 * S - 14 * S - i, oy), fill=(255, 140, 70, a))
        od.point((600 * S + 14 * S + i, oy), fill=(255, 140, 70, a))
    dm = 7 * S
    od.polygon([(600 * S, oy - dm), (600 * S + dm, oy), (600 * S, oy + dm), (600 * S - dm, oy)], outline=(255, 175, 95, 230), width=S)
    img.alpha_composite(orn.filter(ImageFilter.GaussianBlur(3 * S)))
    img.alpha_composite(orn)

    d = ImageDraw.Draw(img)
    line1 = "Таблица лидеров · матчи · игроки · рекорды · правила"
    d.text(((W - d.textlength(line1, font=foot)) / 2, 492 * S), line1, font=foot, fill=(206, 200, 226))
    url = "nlrating.netlify.app"
    d.text(((W - d.textlength(url, font=url_f)) / 2, 532 * S), url, font=url_f, fill=(255, 190, 120))

    img.convert("RGB").resize((1200, 630), Image.LANCZOS).save(out, optimize=True)
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "og.png")
