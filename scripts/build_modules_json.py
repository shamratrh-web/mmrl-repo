#!/usr/bin/env python3
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "json" / "config.json"
DEVICE_MODULES_PATH = ROOT / "json" / "device_modules.json"
TRACKED_MODULES_PATH = ROOT / "json" / "tracked_modules.json"
MODULES_DIR = ROOT / "modules"
OUTPUT_PATH = ROOT / "json" / "modules.json"

MODULE_META = {
    "yt-morphe": {
        "name": "YouTube Morphe",
        "author": "NoName-exe",
        "description": "Root Morphe / ReVanced eXtended YouTube module mirrored for MMRL.",
        "support": "https://github.com/NoName-exe/revanced-extended/issues",
        "readme": "https://raw.githubusercontent.com/NoName-exe/revanced-extended/main/README.md",
        "verified": False,
    },
    "ytm-morphe-arm64": {
        "name": "YouTube Music Morphe (arm64-v8a)",
        "author": "NoName-exe",
        "description": "Root Morphe / ReVanced eXtended YouTube Music module for arm64-v8a, mirrored for MMRL.",
        "support": "https://github.com/NoName-exe/revanced-extended/issues",
        "readme": "https://raw.githubusercontent.com/NoName-exe/revanced-extended/main/README.md",
        "verified": False,
    },
    "ytm-morphe-arm": {
        "name": "YouTube Music Morphe (arm-v7a)",
        "author": "NoName-exe",
        "description": "Root Morphe / ReVanced eXtended YouTube Music module for arm-v7a, mirrored for MMRL.",
        "support": "https://github.com/NoName-exe/revanced-extended/issues",
        "readme": "https://raw.githubusercontent.com/NoName-exe/revanced-extended/main/README.md",
        "verified": False,
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def fetch_size(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            size = resp.headers.get("Content-Length")
            return int(size) if size else None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def parse_track(path: Path) -> dict:
    data = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            data[key] = value.lower() == "true"
        else:
            try:
                data[key] = int(value)
            except ValueError:
                try:
                    data[key] = float(value)
                except ValueError:
                    data[key] = value
    return data


def build_track_module(track: dict, now: float) -> dict:
    upstream = fetch_json(track["update_to"])
    meta = MODULE_META.get(track["id"], {})
    size = fetch_size(upstream["zipUrl"])

    version_entry = {
        "timestamp": now,
        "version": upstream["version"],
        "versionCode": upstream["versionCode"],
        "zipUrl": upstream["zipUrl"],
        "changelog": upstream.get("changelog", ""),
    }
    if size is not None:
        version_entry["size"] = size

    module = {
        "id": track["id"],
        "name": track.get("name") or meta.get("name") or track["id"],
        "version": upstream["version"],
        "versionCode": upstream["versionCode"],
        "author": track.get("author") or meta.get("author") or "unknown",
        "description": track.get("description") or meta.get("description") or "",
        "added": track.get("added", now),
        "support": track.get("support") or meta.get("support"),
        "readme": track.get("readme") or meta.get("readme"),
        "verified": track.get("verified", meta.get("verified", False)),
        "timestamp": now,
        "track": {
            "type": "ONLINE_JSON",
            "added": track.get("added", now),
            "source": track["source"],
            "antifeatures": None,
        },
        "versions": [version_entry],
    }
    if size is not None:
        module["size"] = size
    note = track.get("note")
    if note:
        module["note"] = note
    return module


def build_modules(now: float) -> list[dict]:
    tracked_modules = []
    tracked_ids = set()
    if TRACKED_MODULES_PATH.exists():
        data = load_json(TRACKED_MODULES_PATH)
        for track in data.get("modules") or []:
            tracked_modules.append(build_track_module(track, now))
            tracked_ids.add(track["id"])

    if DEVICE_MODULES_PATH.exists():
        data = load_json(DEVICE_MODULES_PATH)
        snapshot_modules = [
            module for module in (data.get("modules") or [])
            if module.get("id") not in tracked_ids
        ]
        if tracked_modules or snapshot_modules:
            return tracked_modules + snapshot_modules

    modules = []
    for track_path in sorted(MODULES_DIR.glob("*/track.yaml")):
        track = parse_track(track_path)
        if not track.get("enable", True):
            continue
        modules.append(build_track_module(track, now))
    return modules


def main() -> None:
    config = load_json(CONFIG_PATH)
    now = float(int(time.time()))
    modules = build_modules(now)

    modules_json = {
        "name": config["name"],
        "website": config.get("website"),
        "support": config.get("support"),
        "donate": config.get("donate"),
        "submission": config.get("submission"),
        "cover": f'{config["base_url"]}assets/cover.webp',
        "description": config.get("description"),
        "metadata": {
            "version": 1,
            "timestamp": now,
        },
        "modules": modules,
    }

    OUTPUT_PATH.write_text(json.dumps(modules_json, indent=2) + "\n")


if __name__ == "__main__":
    main()
