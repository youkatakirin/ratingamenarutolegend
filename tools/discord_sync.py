"""Copy new posts of the results channel into the repository.

    DISCORD_BOT_TOKEN=... python3 tools/discord_sync.py

Runs from .github/workflows/discord-sync.yml. Only the Python standard library.
Writes:
  discord/inbox.json   posts not yet on the site: text, time, screenshots, game number
  discord/files/       the screenshots in full size
  discord/next.json    number of the next game, read by the result form

Post numbers come from the order of result posts, not from what the organizer typed:
"typed" keeps the typed number so a mismatch can be seen. Posts of games already in
index.html are removed on the next run, with their screenshots.
"""
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
MAX_FILE = 15 * 1024 * 1024
RESULT = re.compile(r"^\s*Рейтинговая\s+игра", re.I)
TYPED = re.compile(r"#\s*(\d+)")


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


def fetch_since(after, token):
    """All posts newer than `after`, oldest first."""
    out, before = [], None
    while True:
        url = f"{API}/channels/{CHANNEL}/messages?limit=100"
        if before:
            url += "&before=" + before
        page = json.loads(get(url, token))
        fresh = [m for m in page if int(m["id"]) > int(after)]
        out.extend(fresh)
        if len(page) < 100 or len(fresh) < len(page):
            break
        before = page[-1]["id"]
    return sorted(out, key=lambda m: int(m["id"]))


def is_result(text):
    return bool(RESULT.search(text)) and "обедитель" in text


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
    return names


def drop_files(entry):
    for rel in entry.get("files", []):
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            os.remove(path)


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


def write_if_changed(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    old = open(path, encoding="utf8").read() if os.path.exists(path) else ""
    if text != old:
        with open(path, "w", encoding="utf8") as f:
            f.write(text)


def main():
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
        text = m.get("content", "")
        if m.get("type", 0) not in (0, 19) or not (text or m.get("attachments")):
            continue
        old = known.get(m["id"])
        typed = TYPED.search(text.split("\n")[0]) if is_result(text) else None
        e = {
            "id": m["id"],
            "time": m["timestamp"],
            "edited": m.get("edited_timestamp"),
            "author": m.get("author", {}).get("global_name") or m.get("author", {}).get("username", ""),
            "result": is_result(text),
            "typed": int(typed.group(1)) if typed else None,
            "text": text,
            "files": (old or {}).get("files") or save_files(m),
        }
        entries.append(e)
    for e in state["messages"]:
        if e["id"] not in seen:
            drop_files(e)  # the post was deleted in the channel
    state["messages"] = entries
    prune(state, site_last_game())
    last = number(state)
    write_if_changed(INBOX, state)
    write_if_changed(NEXT, {"next": last + 1})
    print(f"{len(state['messages'])} posts waiting, next game #{last + 1}")


if __name__ == "__main__":
    main()
