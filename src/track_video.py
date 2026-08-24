#!/usr/bin/env python3
"""Altata House — Video/Media Library.
Stores videos shared by Gerardo with tags for later retrieval.

Usage:
  python3 track_video.py add <url> <title> <tags_csv> [notes]
  python3 track_video.py list [tag]
  python3 track_video.py search <query>
  python3 track_video.py csv
"""
import os
import sys
import yaml
import csv
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_DIR = os.path.join(DATA_DIR, 'csv')
VIDEOS_PATH = os.path.join(DATA_DIR, 'videos.yml')
CSV_PATH = os.path.join(CSV_DIR, 'videos.csv')


def load_videos():
    if not os.path.exists(VIDEOS_PATH):
        return {"videos": []}
    with open(VIDEOS_PATH) as f:
        data = yaml.safe_load(f)
        return data if data else {"videos": []}


def save_videos(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VIDEOS_PATH, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def export_csv():
    data = load_videos()
    os.makedirs(CSV_DIR, exist_ok=True)
    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Date Saved", "URL", "Title", "Tags", "Notes"])
        for v in data.get("videos", []):
            writer.writerow([
                v.get("saved_at"),
                v.get("url"),
                v.get("title"),
                ", ".join(v.get("tags", [])),
                v.get("notes", "")
            ])
    print(f"CSV exported: {CSV_PATH}")


def add_video(url, title, tags, notes=""):
    data = load_videos()
    # Avoid exact duplicates
    for v in data.get("videos", []):
        if v.get("url") == url:
            return False, f"Already saved: {v['title']} ({v['saved_at']})"

    entry = {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "url": url,
        "title": title,
        "tags": [t.strip().lower() for t in tags.split(",") if t.strip()],
        "notes": notes.strip()
    }
    data["videos"].append(entry)
    save_videos(data)
    export_csv()
    return True, entry


def list_videos(tag=None):
    data = load_videos()
    videos = data.get("videos", [])
    if not videos:
        print("No videos saved yet.")
        return
    if tag:
        videos = [v for v in videos if tag.lower() in [t.lower() for t in v.get("tags", [])]]
    print(f"📼 Video Library ({len(videos)} saved):\n")
    for v in reversed(videos):
        tags = ", ".join(f"#{t}" for t in v.get("tags", []))
        print(f"• {v['title']}")
        print(f"  URL: {v['url']}")
        print(f"  Saved: {v['saved_at']} | Tags: {tags}")
        if v.get("notes"):
            print(f"  Notes: {v['notes']}")
        print()


def search_videos(query):
    data = load_videos()
    q = query.lower()
    matches = [v for v in data.get("videos", []) if
               q in v.get("title", "").lower() or
               q in v.get("url", "").lower() or
               q in " ".join(v.get("tags", [])).lower() or
               q in v.get("notes", "").lower()]
    if not matches:
        print(f"No videos match '{query}'.")
        return
    print(f"🔍 Found {len(matches)} match(es) for '{query}':\n")
    for v in reversed(matches):
        print(f"• {v['title']} — {v['url']} (saved {v['saved_at']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 5:
            print("Usage: track_video.py add <url> <title> <tags_csv> [notes]")
            sys.exit(1)
        url, title, tags = sys.argv[2], sys.argv[3], sys.argv[4]
        notes = sys.argv[5] if len(sys.argv) > 5 else ""
        ok, res = add_video(url, title, tags, notes)
        if ok:
            print(f"✅ Saved video:\n  Title: {res['title']}\n  URL: {res['url']}\n  Tags: {', '.join('#'+t for t in res['tags'])}")
        else:
            print(f"⚠️ {res}")
    elif cmd == "list":
        tag = sys.argv[2] if len(sys.argv) > 2 else None
        list_videos(tag)
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: track_video.py search <query>")
            sys.exit(1)
        search_videos(sys.argv[2])
    elif cmd == "csv":
        export_csv()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
