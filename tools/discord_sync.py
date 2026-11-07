"""Copy new posts of the results channel into the repository.

    DISCORD_BOT_TOKEN=... python3 tools/discord_sync.py

Runs from .github/workflows/discord-sync.yml. Only the Python standard library.
Writes:
  discord/inbox.json   posts not yet on the site: text, time, screenshots, game number
  discord/files/       the screenshots in full size
  discord/next.json    number of the next game, read by the result form

Each result post also gets "ac": the match found on ac.narutolegend.dog by time, nicks
and bans (null until it appears there). Nothing here decides anything: the numbers wait
for a person or Claude to enter them.

    python3 tools/discord_sync.py --ac 7648   prints how a match page is read

Post numbers come from the order of result posts, not from what the organizer typed:
"typed" keeps the typed number so a mismatch can be seen. Posts of games already in
index.html are removed on the next run, with their screenshots.
"""
import calendar
import html.parser
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("DISCORD_API", "https://discord.com/api/v10")
CHANNEL = os.environ.get("DISCORD_CHANNEL", "1180907593493925958")
INBOX = os.path.join(ROOT, "discord", "inbox.json")
NEXT = os.path.join(ROOT, "discord", "next.json")
FILES = os.path.join(ROOT, "discord", "files")
AGENT = "ImmortalRating (https://github.com/youkatakirin/ratingamenarutolegend, 1.0)"
AC = os.environ.get("AC_SITE", "https://ac.narutolegend.dog")
AC_WINDOW = 45 * 60      # a match ends within minutes of its post
AC_GIVE_UP = 24 * 3600   # stop looking for a post this old
AC_SCAN = 60             # newest match pages to look through per run
MAX_FILE = 15 * 1024 * 1024
RESULT = re.compile(r"Рейтинговая\s+игра|Rating\s+Games?", re.I)
TYPED = re.compile(r"(?<![<\d])#\s*(\d{1,4})\b")


def get(url, token=None):
    headers = {"User-Agent": AGENT}
    if token:
        headers["Authorization"] = "Bot " + token
    for _ in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read() or b"{}").get("retry_after", 2)) + 0.5)
                continue
            if e.code in (401, 403):
                sys.exit(f"Discord refused access ({e.code}): check the bot token, Message Content Intent and the bot's access to the channel")
            raise
    sys.exit("Discord keeps rate limiting, will try on the next run")


def check_access(page):
    """Without Message Content Intent Discord answers normally but blanks every post."""
    posts = [m for m in page if m.get("type", 0) in (0, 19)]
    if posts and not any(m.get("content") or m.get("attachments") or m.get("embeds") or m.get("message_snapshots") for m in posts):
        sys.exit("Posts come back empty: turn on Message Content Intent for the bot")
    if posts:
        print(f"channel ok, latest post {posts[0]['id']} from {posts[0]['timestamp'][:16]}, {len(posts[0].get('content', ''))} chars")


def fetch_since(after, token):
    """All posts newer than `after`, oldest first."""
    out, before = [], None
    while True:
        url = f"{API}/channels/{CHANNEL}/messages?limit=100"
        if before:
            url += "&before=" + before
        page = json.loads(get(url, token))
        if not before:
            check_access(page)
        fresh = [m for m in page if int(m["id"]) > int(after)]
        out.extend(fresh)
        if len(page) < 100 or len(fresh) < len(page):
            break
        before = page[-1]["id"]
    return sorted(out, key=lambda m: int(m["id"]))


def is_result(text):
    # Organizers write it plain or with Discord markdown: "## Rating Games # 53", "- Победитель: **Альянс**"
    return bool(text) and bool(RESULT.search(text.split("\n")[0])) and "обедитель" in text


def unforward(msg):
    """A forwarded post keeps its content in message_snapshots: lift it onto the message."""
    for snap in msg.get("message_snapshots", []):
        inner = snap.get("message", {})
        msg["content"] = msg.get("content") or inner.get("content", "")
        msg["embeds"] = msg.get("embeds", []) + inner.get("embeds", [])
        msg["attachments"] = msg.get("attachments", []) + inner.get("attachments", [])
    return msg


def embed_text(msg):
    """Result bots post an embed instead of text: flatten it so the rest works the same."""
    out = []
    for em in msg.get("embeds", []):
        for part in (em.get("author", {}).get("name"), em.get("title"), em.get("description")):
            if part:
                out.append(part.strip())
        for f in em.get("fields", []):
            out.append(f"{f.get('name', '').strip()}:\n{f.get('value', '').strip()}")
        if em.get("footer", {}).get("text"):
            out.append(em["footer"]["text"].strip())
    return "\n".join(out)


def embed_result(text):
    low = text.lower()
    return "итог" in low.split("\n")[0] and "обедитель" in text


def site_last_game():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf8").read()
    block = re.search(r'id="season-data">(.*?)</script>', html, re.S).group(1)
    return max(m["n"] for m in json.loads(block)["matches"])


def save_files(msg):
    names = []
    for i, a in enumerate(msg.get("attachments", [])):
        if not (a.get("content_type") or "").startswith("image/") or a.get("size", 0) > MAX_FILE:
            continue
        ext = os.path.splitext(a.get("filename", ""))[1].lower() or ".png"
        rel = f"discord/files/{msg['id']}-{i}{ext}"
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            os.makedirs(FILES, exist_ok=True)
            with open(path, "wb") as f:
                f.write(get(a["url"]))
        names.append(rel)
    for i, em in enumerate(msg.get("embeds", [])):
        url = (em.get("image") or {}).get("url") or (em.get("thumbnail") or {}).get("url")
        if not url:
            continue
        rel = f"discord/files/{msg['id']}-e{i}.png"
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            data = get(url)
            if len(data) > MAX_FILE:
                continue
            os.makedirs(FILES, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        names.append(rel)
    return names


def drop_files(entry):
    for rel in entry.get("files", []):
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            os.remove(path)


def site_recent():
    """The last games already on the site, as (UTC time, nicks text, label)."""
    html = open(os.path.join(ROOT, "index.html"), encoding="utf8").read()
    block = re.search(r'id="season-data">(.*?)</script>', html, re.S).group(1)
    out = []
    for m in json.loads(block)["matches"][-3:]:
        stamp = re.match(r"(\d+)-(\d+)-(\d+)T(\d+):(\d+)", m["date"])
        when = calendar.timegm(tuple(int(x) for x in stamp.groups()) + (0,)) - 5 * 3600  # site times are UTC+5
        nicks = " ".join(r["p"] for r in m.get("alliance", []) + m.get("akatsuki", []))
        out.append((when, nicks.lower(), f"site#{m['n']}", m.get("src")))
    return out


def mark_duplicates(entries):
    """A result bot may summarise a game that already has a written post: count it once."""
    seen = site_recent()
    for e in entries:
        if not e["result"]:
            continue
        if e.get("embed"):
            nicks = [n.strip().lower() for n in re.findall(r"—\s*(\S[^\n]*)", e["text"])]
            for when, low, label, _ in seen:
                if len(nicks) >= 6 and abs(post_time(e) - when) <= 40 * 60 and sum(n in low for n in nicks) >= 5:
                    e["result"], e["dup_of"] = False, label
                    break
        if e["result"]:
            seen.append((post_time(e), e["text"].lower(), e["id"], None))


def drop_known_ac(state):
    """A match whose ac page is already on the site is a repeat summary."""
    srcs = {s for *_, s in site_recent() if s}
    for e in state["messages"]:
        if e["result"] and (e.get("ac") or {}).get("src") in srcs:
            e["result"], e["dup_of"] = False, f"ac#{e['ac']['src']}"


def number(state):
    n = state["base_game"]
    for e in state["messages"]:
        if e["result"]:
            n += 1
            e["game"] = n
    return n


def prune(state, site_last):
    """Forget everything up to the last game the site already has."""
    number(state)
    done = [e for e in state["messages"] if e["result"] and e["game"] <= site_last]
    if site_last <= state["base_game"] and not done:
        return
    edge = int(done[-1]["id"]) if done else 0
    keep = []
    for e in state["messages"]:
        if int(e["id"]) <= edge:
            drop_files(e)
        else:
            keep.append(e)
    state["messages"] = keep
    state["base_game"] = max(site_last, state["base_game"])
    if edge:
        state["after"] = str(edge)


class Page(html.parser.HTMLParser):
    """Text of a page without scripts, plus its table rows."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.text = []
        self.rows = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "tr":
            self.rows.append([])
        elif tag == "td" and self.rows:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag == "td" and self.cell is not None:
            self.rows[-1].append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None

    def handle_data(self, data):
        if self.skip:
            return
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def number_of(text):
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else 0


def ac_match(src):
    """One match page as data, or None when it has no stats yet."""
    page = Page()
    try:
        page.feed(get(f"{AC}/match/{src}").decode("utf8", "replace"))
    except urllib.error.HTTPError:
        return None
    text = re.sub(r"\s+", " ", " ".join(page.text))
    head = re.search(r"(\d{1,2})\.(\d{2})\.(\d{4}),\s*(\d{2}):(\d{2}):\d{2}\s*Матч\s*#\d+\s*(?:(\d+)\s*:\s*(\d+)\s*убийства\s*)?(\d+:\d{2})?", text)
    if not head:
        return None
    day, month, year, hour, minute = (int(x) for x in head.group(1, 2, 3, 4, 5))
    players = []
    for r in page.rows:
        if len(r) < 7 or "/" not in r[2]:
            continue
        kda = [int(x) for x in r[2].split("/")]
        hero = r[1][2:] if r[1] != "—" else ""
        if not hero or not sum(kda) + number_of(r[3]):
            continue  # a spectator's slot
        players.append({
            "nick": re.sub(r"\s*MVP$", "", r[0]),
            "mvp": r[0].endswith("MVP"),
            "hero": hero, "kda": kda, "cs": number_of(r[3]), "gold": number_of(r[4]),
            "dmg": number_of(r[5]), "lvl": number_of(r[6]),
        })
    if not players:
        return None
    return {
        "src": src,
        "ends_utc": calendar.timegm((year, month, day, hour - 3, minute, 0)),  # the site shows Moscow time
        "kills": [int(head.group(6)), int(head.group(7))] if head.group(6) else None,
        "duration_ac": head.group(8),
        "players": players,
    }


def post_time(entry):
    stamp = re.match(r"(\d+)-(\d+)-(\d+)T(\d+):(\d+)", entry["time"])
    return calendar.timegm(tuple(int(x) for x in stamp.groups()) + (0,))


def fits(entry, m):
    """Nicks can be spoofed on either side, so a few misses are fine if the bans agree."""
    text = entry["text"].lower()
    lines = text.split("\n")
    bans = next((" ".join(lines[i:i + 2]) for i, l in enumerate(lines) if "баны" in l), "")  # embeds put the heroes on the next line
    nicks = sum(p["nick"].lower().strip("_") in text for p in m["players"])
    heroes = sum(p["hero"].lower() in bans for p in m["players"])
    if entry.get("embed") and not bans:
        return nicks >= 4  # bot summaries have no bans line
    return nicks >= 6 or (nicks >= 4 and heroes >= 3)


def find_ac(state):
    """Fill in "ac" for result posts that still miss it."""
    now = time.time()
    want = [e for e in state["messages"] if e["result"] and not e.get("ac") and now - post_time(e) < AC_GIVE_UP]
    if not want:
        return
    listing = get(f"{AC}/matches").decode("utf8", "replace")
    ids = sorted({int(x) for x in re.findall(r"/match/(\d+)", listing)}, reverse=True)
    if not ids:
        return
    floor = max(state.get("ac_after", 0), ids[0] - AC_SCAN)
    for src in range(ids[0], floor, -1):
        if not want:
            break
        m = ac_match(src)
        time.sleep(0.2)
        if not m:
            continue
        for e in want:
            if abs(post_time(e) - m["ends_utc"]) <= AC_WINDOW and fits(e, m):
                e["ac"] = m
                state["ac_after"] = max(state.get("ac_after", 0), src)
                want.remove(e)
                break


def write_if_changed(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    old = open(path, encoding="utf8").read() if os.path.exists(path) else ""
    if text != old:
        with open(path, "w", encoding="utf8") as f:
            f.write(text)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--ac":
        print(json.dumps([ac_match(int(x)) for x in sys.argv[2].split(",")], ensure_ascii=False))
        return
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("DISCORD_BOT_TOKEN is not set yet, nothing to do")
        return
    state = json.load(open(INBOX, encoding="utf8"))
    posts = fetch_since(state["after"], token)
    known = {e["id"]: e for e in state["messages"]}
    seen = set()
    entries = []
    for m in posts:
        seen.add(m["id"])
        unforward(m)
        text = m.get("content", "")
        embed = embed_text(m)
        if embed:
            text = (text + "\n" + embed).strip() if text else embed
        if m.get("type", 0) not in (0, 19) or not (text or m.get("attachments")):
            continue
        old = known.get(m["id"])
        result = is_result(text) or bool(embed and embed_result(embed))
        typed = TYPED.search(text.split("\n")[0]) if result else None
        e = {
            "id": m["id"],
            "time": m["timestamp"],
            "edited": m.get("edited_timestamp"),
            "author": m.get("author", {}).get("global_name") or m.get("author", {}).get("username", ""),
            "result": result,
            "embed": bool(embed),
            "typed": int(typed.group(1)) if typed else None,
            "text": text,
            "files": (old or {}).get("files") or save_files(m),
            "ac": (old or {}).get("ac"),
        }
        entries.append(e)
    for e in state["messages"]:
        if e["id"] not in seen:
            drop_files(e)  # the post was deleted in the channel
    mark_duplicates(entries)
    state["messages"] = entries
    prune(state, site_last_game())
    try:
        find_ac(state)
    except Exception as e:  # ac being down must not cost us the Discord posts
        print("ac.narutolegend.dog is not available this run:", e)
    drop_known_ac(state)
    last = number(state)
    write_if_changed(INBOX, state)
    write_if_changed(NEXT, {"next": last + 1})
    print(f"{len(state['messages'])} posts waiting, next game #{last + 1}")


if __name__ == "__main__":
    main()
