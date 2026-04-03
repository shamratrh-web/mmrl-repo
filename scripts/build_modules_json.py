#!/usr/bin/env python3
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "json" / "config.json"
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
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def fetch_size(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD")
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


def build_module(track: dict, now: float) -> dict:
    upstream = fetch_json(track["update_to"])
    meta = MODULE_META[track["id"]]
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
        "name": meta["name"],
        "version": upstream["version"],
        "versionCode": upstream["versionCode"],
        "author": meta["author"],
        "description": meta["description"],
        "added": track.get("added", now),
        "support": meta["support"],
        "readme": meta["readme"],
        "verified": meta["verified"],
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
    return module


def main() -> None:
    config = load_json(CONFIG_PATH)
    now = float(int(time.time()))
    modules = []

    for track_path in sorted(MODULES_DIR.glob("*/track.yaml")):
        track = parse_track(track_path)
        if not track.get("enable", True):
            continue
        modules.append(build_module(track, now))

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
