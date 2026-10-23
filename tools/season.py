"""Read or replace the season data embedded in index.html.

    python3 tools/season.py get index.html > season.json
    python3 tools/season.py set index.html season.json

The data lives in <script type="application/json" id="season-data">.
"set" validates the JSON and the match records before writing.
"""
import json
import re
import sys

BLOCK = re.compile(
    r'(<script type="application/json" id="season-data">)(.*?)(</script>)', re.S
)


def read_block(html):
    m = BLOCK.search(html)
    if not m:
        sys.exit("season-data block not found")
    return m


def validate(data):
    sides = ("alliance", "akatsuki")
    seen = set()
    for m in data["matches"]:
        n = m["n"]
        if n in seen:
            sys.exit(f"duplicate match number {n}")
        seen.add(n)
        if m["winner"] not in sides or m["firstPick"] not in sides:
            sys.exit(f"match {n}: winner/firstPick must be alliance or akatsuki")
        for side in sides:
            for p in m[side]:
                if not isinstance(p.get("d"), int):
                    sys.exit(f"match {n}: points for {p.get('p')} must be an integer")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("get", "set"):
        sys.exit(__doc__)
    path = sys.argv[2]
    html = open(path, encoding="utf8").read()
    m = read_block(html)
    if sys.argv[1] == "get":
        print(json.dumps(json.loads(m.group(2)), ensure_ascii=False, indent=2))
        return
    data = json.load(open(sys.argv[3], encoding="utf8"))
    validate(data)
    body = "\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    html = html[: m.start(2)] + body + html[m.end(2):]
    open(path, "w", encoding="utf8").write(html)
    print(f"updated {path}: {len(data['matches'])} matches")


if __name__ == "__main__":
    main()
