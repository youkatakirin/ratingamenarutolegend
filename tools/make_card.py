"""Draw "match result" cards (PNG, 1200x675) in the site's style.

    python3 tools/make_card.py index.html            # every match
    python3 tools/make_card.py index.html 5 6        # only games #5 and #6
    python3 tools/make_card.py index.html 5 --also other.html

Writes cards/game-N.png next to index.html and sets "card": "cards/game-N.png"
on those matches in index.html (and in every file passed after --also).
Needs Pillow. Fonts live in tools/fonts (SIL Open Font License).
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
BLOCK = re.compile(r'(<script type="application/json" id="season-data">)(.*?)(</script>)', re.S)

S = 2  # draw at 2x, then downscale
W, H = 1200, 675
BG = (7, 9, 15)
INK = (242, 244, 248)
SOFT = (196, 203, 218)
MUTED = (138, 148, 170)
LINE = (29, 36, 51)
PANEL = (15, 19, 29)
PANEL_2 = (19, 24, 38)
ALLY = (47, 155, 255)
ALLY_DARK = (19, 94, 168)
AKA = (255, 58, 92)
AKA_DARK = (158, 22, 48)
GOLD = (255, 201, 74)
SVP = (143, 198, 255)
WIN = (79, 209, 139)
LOSS = (255, 107, 127)
NAME = {"alliance": "АЛЬЯНС", "akatsuki": "АКАЦУКИ"}
WIN_LABEL = {"alliance": "ПОБЕДА АЛЬЯНСА", "akatsuki": "ПОБЕДА АКАЦУКИ"}


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size * S))


F_TITLE = font("RussoOne.ttf", 72)
F_BADGE = font("RussoOne.ttf", 26)
F_KILLS = font("RussoOne.ttf", 50)
F_TEAM = font("RussoOne.ttf", 24)
F_DELTA = font("RussoOne.ttf", 25)
F_NAME = font("Exo2-SemiBold.ttf", 26)
F_SMALL = font("Exo2-SemiBold.ttf", 18)
F_HERO = font("Exo2-Regular.ttf", 18)
F_KDA = font("Exo2-SemiBold.ttf", 23)
F_AWARD = font("Exo2-SemiBold.ttf", 14)


def s(v):
    return v * S


def glow(img, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * 0.45)))


def spaced(d, x, y, text, f, fill, tracking):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tracking
    return x


def fit(d, text, f, max_w):
    if d.textlength(text, font=f) <= max_w:
        return text
    while text and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def skew_box(img, x0, y0, x1, y1, c0, c1, alpha=255):
    off = (y1 - y0) * math.tan(math.radians(10))
    grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(int(x0), int(x1 + off) + 1):
        t = (x - x0) / max(1, (x1 + off - x0))
        col = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
        gd.line([(x, y0), (x, y1)], fill=col + (alpha,))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon([(x0 + off, y0), (x1 + off, y0), (x1, y1), (x0, y1)], fill=255)
    img.paste(grad, (0, 0), mask)
    return off


def dmy(iso):
    date, _, time = iso.partition("T")
    y, m, dd = date.split("-")
    return f"{dd}.{m}.{y}"


def signed(n):
    # Russo One has no U+2212 minus sign, so negatives use an en dash
    return f"+{n}" if n > 0 else (f"–{abs(n)}" if n < 0 else "0")


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def effects(data):
    """Same point rules as the page: streak bonus (rule 8.1), MVP/SVP bonus (rule 8.3) and automatic blocks (rules 8.5, 2.6)."""
    ban_pts = data.get("points", {}).get("ban", 20)
    award_pts = data.get("points", {}).get("award", 0)
    award_from = data.get("points", {}).get("awardFrom", 1)
    out, streak, lstreak, blocks, played = {}, {}, {}, {}, {}
    extra = sorted(data.get("penalties") or [], key=lambda p: p["date"])
    i, last_n = 0, 0

    def block(name, games_played, info):
        # per player: counter resets after every 50 games that player has played
        key = (name, (max(1, games_played) - 1) // 50)
        blocks[key] = blocks.get(key, 0) + 1
        pts = info.get("points")
        return {"days": info.get("days") or blocks[key], "pts": pts if isinstance(pts, int) else -ban_pts,
                "reason": info.get("reason") or "Штраф"}

    for m in sorted(data["matches"], key=lambda m: m["n"]):
        while i < len(extra) and extra[i]["date"] < m["date"][:10]:
            block(extra[i]["p"], played.get(extra[i]["p"], 0), extra[i])
            i += 1
        last_n = m["n"]
        for side in ("alliance", "akatsuki"):
            won = m["winner"] == side
            for x in m.get(side, []):
                p = x["p"]
                played[p] = played.get(p, 0) + 1
                streak[p] = streak.get(p, 0) + 1 if won else 0
                lstreak[p] = 0 if won else lstreak.get(p, 0) + 1
                bonus = (5 if streak[p] > 5 else 0) if won else (-5 if lstreak[p] > 5 else 0)
                abon = award_pts if x.get("award") in ("MVP", "SVP") and m["n"] >= award_from else 0
                pen = block(p, played[p], x["ban"]) if x.get("ban") else None
                out[(m["n"], p)] = {"total": x["d"] + bonus + abon + (pen["pts"] if pen else 0), "bonus": bonus, "abon": abon, "pen": pen}
    return out


def draw_card(m, out_path, eff=None):
    img = Image.new("RGBA", (s(W), s(H)), BG + (255,))
    glow(img, s(140), s(-60), s(520), ALLY, 80)
    glow(img, s(1080), s(-40), s(500), AKA, 75)
    hatch = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for x in range(-s(H), s(W), s(22)):
        hd.line([(x, s(H)), (x + s(H), 0)], fill=(255, 255, 255, 6), width=S)
    img.alpha_composite(hatch)
    d = ImageDraw.Draw(img)
    M = s(52)

    # eyebrow + meta
    spaced(d, M, s(36), "IMMORTAL · NARUTO LEGEND 3.0", F_SMALL, MUTED, s(3.2))
    meta = [dmy(m["date"])]
    if m.get("duration"):
        meta.append(m["duration"])
    meta.append("организатор " + m.get("org", ""))
    meta_t = " · ".join(meta)
    d.text((s(W) - M - d.textlength(meta_t, font=F_SMALL), s(36)), meta_t, font=F_SMALL, fill=MUTED)

    # title, result badge, kills
    title = f"ИГРА #{m['n']}"
    d.text((M - s(3), s(66)), title, font=F_TITLE, fill=INK)
    tw = d.textlength(title, font=F_TITLE)
    win = m["winner"]
    label = WIN_LABEL[win]
    bw = d.textlength(label, font=F_BADGE) + s(44)
    bx, by0, by1 = M + tw + s(28), s(88), s(136)
    c0, c1 = (ALLY_DARK, ALLY) if win == "alliance" else (AKA, AKA_DARK)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([bx, by0, bx + bw, by1], fill=(ALLY if win == "alliance" else AKA) + (120,))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(16))))
    off = skew_box(img, bx, by0, bx + bw, by1, c0, c1)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), label, font=F_BADGE)
    d.text((bx + off / 2 + s(22), by0 + (by1 - by0 - (bb[3] - bb[1])) / 2 - bb[1]), label, font=F_BADGE, fill=(255, 255, 255))
    if m.get("kills"):
        a, k = m["kills"]
        parts = [(str(a), ALLY), (" : ", MUTED), (str(k), AKA)]
        total = sum(d.textlength(t, font=F_KILLS) for t, _ in parts)
        x = s(W) - M - total
        for t, c in parts:
            d.text((x, s(74)), t, font=F_KILLS, fill=c)
            x += d.textlength(t, font=F_KILLS)
        lab = "УБИЙСТВА"
        d.text((s(W) - M - d.textlength(lab, font=F_SMALL), s(136)), lab, font=F_SMALL, fill=MUTED)

    # teams
    col_w = (s(W) - 2 * M - s(24)) / 2
    top = s(184)
    for i, side in enumerate(("alliance", "akatsuki")):
        x0 = M + i * (col_w + s(24))
        won = m["winner"] == side
        base = ALLY if side == "alliance" else AKA
        dark = ALLY_DARK if side == "alliance" else AKA_DARK
        if won:
            sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).rectangle([x0, top, x0 + col_w, top + s(370)], outline=base + (150,), width=s(6))
            img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(14))))
        d = ImageDraw.Draw(img)
        d.rectangle([x0, top, x0 + col_w, top + s(370)], fill=PANEL + (255,), outline=(base if won else LINE), width=S * (2 if won else 1))
        # header band
        hb0, hb1 = top + s(14), top + s(60)
        if won:
            off = skew_box(img, x0 + s(14), hb0, x0 + col_w - s(22), hb1, dark if side == "alliance" else base, base if side == "alliance" else dark)
        else:
            off = skew_box(img, x0 + s(14), hb0, x0 + col_w - s(22), hb1, PANEL_2, PANEL_2)
        d = ImageDraw.Draw(img)
        tb = d.textbbox((0, 0), NAME[side], font=F_TEAM)
        ty = hb0 + (hb1 - hb0 - (tb[3] - tb[1])) / 2 - tb[1]
        d.text((x0 + s(14) + off / 2 + s(16), ty), NAME[side], font=F_TEAM, fill=(255, 255, 255) if won else base)
        res = "ПОБЕДА" if won else "ПОРАЖЕНИЕ"
        rb = d.textbbox((0, 0), res, font=F_SMALL)
        d.text((x0 + col_w - s(22) + off / 2 - s(16) - d.textlength(res, font=F_SMALL), hb0 + (hb1 - hb0 - (rb[3] - rb[1])) / 2 - rb[1]),
               res, font=F_SMALL, fill=(255, 255, 255) if won else MUTED)
        # players
        y = top + s(74)
        row_h = s(72)
        for j, x in enumerate(m.get(side, [])):
            ry = y + j * row_h
            if j:
                d.line([(x0 + s(16), ry), (x0 + col_w - s(16), ry)], fill=LINE, width=S)
            e = (eff or {}).get((m["n"], x["p"])) or {"total": x["d"], "bonus": 0, "pen": None}
            delta = signed(e["total"])
            dw = d.textlength(delta, font=F_DELTA)
            kda = " / ".join(str(v) for v in x["kda"]) if x.get("kda") else ""
            kw = d.textlength(kda, font=F_KDA) if kda else 0
            right = x0 + col_w - s(18)
            d.text((right - dw, ry + s(20)), delta, font=F_DELTA, fill=WIN if e["total"] > 0 else LOSS if e["total"] < 0 else MUTED)
            if kda:
                d.text((right - dw - s(22) - kw, ry + s(20)), kda, font=F_KDA, fill=SOFT)
            name_max = (right - dw - s(22) - kw - s(16)) - (x0 + s(18))
            award = x.get("award")
            aw = (d.textlength(award, font=F_AWARD) + s(16)) if award else 0
            name = fit(d, x["p"], F_NAME, name_max - (aw + s(10) if award else 0))
            nx = x0 + s(18)
            d.text((nx, ry + s(9)), name, font=F_NAME, fill=INK)
            if award:
                ax = nx + d.textlength(name, font=F_NAME) + s(12)
                ac = GOLD if award == "MVP" else SVP
                ab = d.textbbox((0, 0), award, font=F_AWARD)
                ay0, ay1 = ry + s(17), ry + s(39)
                o = (ay1 - ay0) * math.tan(math.radians(10))
                d.polygon([(ax + o, ay0), (ax + aw + o, ay0), (ax + aw, ay1), (ax, ay1)], outline=ac, width=S)
                d.text((ax + o / 2 + s(8), ay0 + (ay1 - ay0 - (ab[3] - ab[1])) / 2 - ab[1]), award, font=F_AWARD, fill=ac)
            pen = e["pen"]
            ban_t = f"штраф –{abs(pen['pts'])}" if pen else ""
            bonus_t = (f"серия +{e['bonus']}" if e["bonus"] > 0 else f"серия –{abs(e['bonus'])}") if e["bonus"] else ""
            abon_t = f"{x.get('award')} +{e['abon']}" if e.get("abon") else ""
            sub = " · ".join(t for t in (x.get("hero"), ban_t, x.get("note"), abon_t, bonus_t) if t)
            if sub:
                d.text((nx, ry + s(41)), fit(d, sub, F_HERO, name_max), font=F_HERO, fill=LOSS if (pen and not x.get("hero")) else MUTED)

    # footer
    fy = s(582)
    d.line([(M, fy), (s(W) - M, fy)], fill=LINE, width=S)
    bans = m.get("bans") or []
    left = ("Бан на следующие игры: " + " · ".join(bans)) if bans else (m.get("note") or "")
    url = "youkatakirin.github.io/ratingamenarutolegend"
    uw = d.textlength(url, font=F_SMALL)
    d.text((M, fy + s(24)), fit(d, left, F_SMALL, s(W) - 2 * M - uw - s(30)), font=F_SMALL, fill=SOFT)
    d.text((s(W) - M - uw, fy + s(24)), url, font=F_SMALL, fill=MUTED)

    img.convert("RGB").resize((W, H), Image.LANCZOS).save(out_path, optimize=True)


def load(path):
    html = open(path, encoding="utf8").read()
    m = BLOCK.search(html)
    if not m:
        sys.exit(f"season-data block not found in {path}")
    return html, m, json.loads(m.group(2))


def save_cards_field(path, numbers):
    html, m, data = load(path)
    for match in data["matches"]:
        if match["n"] in numbers:
            match["card"] = f"cards/game-{match['n']}.png"
    body = "\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    open(path, "w", encoding="utf8").write(html[: m.start(2)] + body + html[m.end(2):])


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    also = []
    if "--also" in args:
        i = args.index("--also")
        also = args[i + 1:]
        args = args[:i]
    page = args[0]
    wanted = {int(a) for a in args[1:]}
    _, _, data = load(page)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(page)), "cards")
    os.makedirs(out_dir, exist_ok=True)
    done = []
    eff = effects(data)
    for match in data["matches"]:
        if wanted and match["n"] not in wanted:
            continue
        out = os.path.join(out_dir, f"game-{match['n']}.png")
        draw_card(match, out, eff)
        done.append(match["n"])
        print("card", out)
    for path in [page] + also:
        save_cards_field(path, set(done))


if __name__ == "__main__":
    main()
