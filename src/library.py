#!/usr/bin/env python3
"""Altata House — Unified Read-Later Library.

Stores videos, links, articles, and notes with tags + a value rating so the
user can rank what to read/watch later.

Each item:
  id          : short unique id (e.g. 'v1', 'l1', 'a1')
  type        : video | link | article | note
  title       : display title
  url         : source URL
  tags        : list of tags
  value       : high | medium | low   (priority for reading later)
  summary     : short AI summary / why it matters
  saved_at    : date
"""
import os
import sys
import yaml
import csv
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_DIR = os.path.join(DATA_DIR, 'csv')

LIB_PATH = os.path.join(DATA_DIR, 'library.yml')
CSV_PATH = os.path.join(CSV_DIR, 'library.csv')

VALID_TYPES = ["video", "link", "article", "note"]
VALID_VALUES = ["high", "medium", "low"]


def load():
    if not os.path.exists(LIB_PATH):
        return {"items": []}
    with open(LIB_PATH) as f:
        data = yaml.safe_load(f)
        return data if data else {"items": []}


def save(data):
    with open(LIB_PATH, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    export_csv(data)


def export_csv(data):
    os.makedirs(CSV_DIR, exist_ok=True)
    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Type", "Title", "URL", "Tags", "Value", "Summary", "Saved At"])
        for item in data.get("items", []):
            writer.writerow([
                item.get("id"),
                item.get("type"),
                item.get("title"),
                item.get("url"),
                ";".join(item.get("tags", [])),
                item.get("value"),
                item.get("summary"),
                item.get("saved_at")
            ])


def next_id(items, prefix):
    n = len([i for i in items if i.get("id", "").startswith(prefix)])
    return f"{prefix}{n + 1}"


def add(item_type, title, url="", tags=None, value="medium", summary=""):
    if item_type not in VALID_TYPES:
        return False, f"Invalid type '{item_type}'. Must be one of {VALID_TYPES}"
    if value not in VALID_VALUES:
        return False, f"Invalid value '{value}'. Must be one of {VALID_VALUES}"

    data = load()
    items = data["items"]

    # Avoid duplicates by URL
    if url and any(i.get("url") == url for i in items):
        return False, f"Already in library: {url}"

    prefix = {"video": "v", "link": "l", "article": "a", "note": "n"}[item_type]
    item = {
        "id": next_id(items, prefix),
        "type": item_type,
        "title": title,
        "url": url,
        "tags": tags or [],
        "value": value,
        "summary": summary,
        "saved_at": datetime.now().strftime("%Y-%m-%d")
    }
    items.append(item)
    save(data)
    return True, item


def remove(item_id):
    data = load()
    items = data["items"]
    before = len(items)
    data["items"] = [i for i in items if i.get("id") != item_id]
    if len(data["items"]) == before:
        return False, f"No item with id '{item_id}'"
    save(data)
    return True, f"Removed {item_id}"


def search(query):
    data = load()
    q = query.lower()
    results = []
    for i in data["items"]:
        haystack = " ".join([
            i.get("title", ""), i.get("url", ""), i.get("summary", ""),
            " ".join(i.get("tags", []))
        ]).lower()
        if q in haystack:
            results.append(i)
    return results


def get_text_list(tag=None, item_type=None, value=None, limit=None):
    data = load()
    items = data["items"]
    if tag:
        items = [i for i in items if tag.lower() in [t.lower() for t in i.get("tags", [])]]
    if item_type:
        items = [i for i in items if i.get("type") == item_type]
    if value:
        items = [i for i in items if i.get("value") == value]

    # Sort: high value first, then by saved date
    order = {"high": 0, "medium": 1, "low": 2}
    items = sorted(items, key=lambda i: (order.get(i.get("value", "medium"), 1), i.get("saved_at", "")), reverse=False)

    if limit:
        items = items[:limit]

    if not items:
        return "📭 Library is empty."

    lines = ["📚 **ALTATA HOUSE — READ LATER LIBRARY**", "────────────────────────"]
    for i in items:
        val_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(i.get("value"), "⚪")
        type_icon = {"video": "🎬", "link": "🔗", "article": "📄", "note": "📝"}.get(i.get("type"), "📌")
        tags = " ".join(f"`#{t}`" for t in i.get("tags", []))
        lines.append(f"\n{val_icon} {type_icon} **{i.get('title')}**")
        lines.append(f"   ID: `{i.get('id')}` | Value: **{i.get('value')}** | Saved: {i.get('saved_at')}")
        if i.get("url"):
            lines.append(f"   🔗 {i.get('url')}")
        if i.get("summary"):
            lines.append(f"   💡 {i.get('summary')}")
        if tags:
            lines.append(f"   {tags}")
    return "\n".join(lines)


def print_help():
    print("Usage:")
    print("  library.py add <type> <title> [--url URL] [--tags t1,t2] [--value high|medium|low] [--summary TEXT]")
    print("  library.py list [--tag X] [--type Y] [--value Z] [--limit N]")
    print("  library.py search <query>")
    print("  library.py remove <id>")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print_help()
        sys.exit(1)

    cmd = args[0]

    if cmd == "add":
        if len(args) < 3:
            print("Error: library.py add <type> <title> ...")
            sys.exit(1)
        item_type = args[1]
        title = args[2]
        url = ""
        tags = []
        value = "medium"
        summary = ""
        i = 3
        while i < len(args):
            if args[i] == "--url" and i + 1 < len(args):
                url = args[i + 1]; i += 2
            elif args[i] == "--tags" and i + 1 < len(args):
                tags = [t.strip() for t in args[i + 1].split(",") if t.strip()]; i += 2
            elif args[i] == "--value" and i + 1 < len(args):
                value = args[i + 1]; i += 2
            elif args[i] == "--summary" and i + 1 < len(args):
                summary = args[i + 1]; i += 2
            else:
                i += 1
        ok, res = add(item_type, title, url, tags, value, summary)
        if ok:
            print(f"SUCCESS: Saved '{res['title']}' as {res['id']} ({res['type']}, value={res['value']})")
        else:
            print(f"ERROR: {res}")
            sys.exit(1)

    elif cmd == "list":
        tag = None
        item_type = None
        value = None
        limit = None
        i = 1
        while i < len(args):
            if args[i] == "--tag" and i + 1 < len(args):
                tag = args[i + 1]; i += 2
            elif args[i] == "--type" and i + 1 < len(args):
                item_type = args[i + 1]; i += 2
            elif args[i] == "--value" and i + 1 < len(args):
                value = args[i + 1]; i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1]); i += 2
            else:
                i += 1
        print(get_text_list(tag, item_type, value, limit))

    elif cmd == "search":
        if len(args) < 2:
            print("Error: library.py search <query>")
            sys.exit(1)
        results = search(" ".join(args[1:]))
        if not results:
            print("No matches found.")
            sys.exit(0)
        lines = ["🔍 **SEARCH RESULTS**", "────────────────────────"]
        for i in results:
            val_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(i.get("value"), "⚪")
            type_icon = {"video": "🎬", "link": "🔗", "article": "📄", "note": "📝"}.get(i.get("type"), "📌")
            lines.append(f"\n{val_icon} {type_icon} **{i.get('title')}** (`{i.get('id')}`)")
            if i.get("url"):
                lines.append(f"   🔗 {i.get('url')}")
            if i.get("summary"):
                lines.append(f"   💡 {i.get('summary')}")
        print("\n".join(lines))

    elif cmd == "remove":
        if len(args) < 2:
            print("Error: library.py remove <id>")
            sys.exit(1)
        ok, res = remove(args[1])
        print(res)
        if not ok:
            sys.exit(1)

    else:
        print(f"Unknown command: '{cmd}'")
        sys.exit(1)
