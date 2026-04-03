#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "json" / "config.json"
DEVICE_MODULES_PATH = ROOT / "json" / "device_modules.json"
BUILD_SCRIPT = ROOT / "scripts" / "build_modules_json.py"
TERMUX_PREFIX = Path("/data/data/com.termux/files/usr/bin")
ZIP_BIN = TERMUX_PREFIX / "zip"
GH_BIN = TERMUX_PREFIX / "gh"
PYTHON_BIN = TERMUX_PREFIX / "python"
REPO_SLUG = "shamratrh-web/mmrl-repo"
RELEASE_TAG = "device-snapshot"
PAGES_BASE = "https://shamratrh-web.github.io/mmrl-repo/"
RELEASE_BASE = f"https://github.com/{REPO_SLUG}/releases/download/{RELEASE_TAG}"
SOURCE_ROOT = "/data/adb/modules"
EXCLUDED_DIRS = {
    ".TA_utl",
    "zn_magisk_compat",
}
EXCLUDED_FILES = {
    "disable",
    "remove",
    "update",
}
UPDATE_BINARY = """#!/sbin/sh

#################
# Initialization
#################

umask 022

# echo before loading util_functions
ui_print() { echo "$1"; }

require_new_magisk() {
  ui_print "*******************************"
  ui_print " Please install Magisk v20.4+! "
  ui_print "*******************************"
  exit 1
}

#########################
# Load util_functions.sh
#########################

OUTFD=$2
ZIPFILE=$3

mount /data 2>/dev/null

[ -f /data/adb/magisk/util_functions.sh ] || require_new_magisk
. /data/adb/magisk/util_functions.sh
[ $MAGISK_VER_CODE -lt 20400 ] && require_new_magisk

install_module
exit 0
"""
UPDATER_SCRIPT = "#MAGISK\n"


def run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def run_stdout(cmd: list[str]) -> str:
    return run(cmd).stdout


def run_root(script: str) -> str:
    return run_stdout(["su", "-c", script])


def read_props(module_dir: str) -> dict[str, str]:
    props = {}
    output = run_root(f"sed -n '1,200p' '{module_dir}/module.prop'")
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def list_modules() -> list[dict]:
    output = run_root(f"find {SOURCE_ROOT} -mindepth 1 -maxdepth 1 -type d | sort")
    modules = []
    for line in output.splitlines():
        path = line.strip()
        if not path:
            continue
        module_id = Path(path).name
        if module_id.startswith(".") or module_id in EXCLUDED_DIRS:
            continue
        try:
            props = read_props(path)
        except subprocess.CalledProcessError:
            continue
        if not props.get("id"):
            continue
        remove = bool(run(["su", "-c", f"test -f '{path}/remove'"], check=False).returncode == 0)
        if remove:
            continue
        disabled = bool(run(["su", "-c", f"test -f '{path}/disable'"], check=False).returncode == 0)
        modules.append(
            {
                "path": path,
                "id": props.get("id", module_id),
                "name": props.get("name", module_id),
                "version": props.get("version", "unknown"),
                "versionCode": int(str(props.get("versionCode", "0")).strip() or "0"),
                "author": props.get("author", "unknown"),
                "description": props.get("description", ""),
                "updateJson": props.get("updateJson", ""),
                "disabled": disabled,
            }
        )
    return sorted(modules, key=lambda item: item["id"])


def write_installer_files(staging_dir: Path) -> None:
    updater_dir = staging_dir / "META-INF" / "com" / "google" / "android"
    updater_dir.mkdir(parents=True, exist_ok=True)
    (updater_dir / "update-binary").write_text(UPDATE_BINARY)
    (updater_dir / "updater-script").write_text(UPDATER_SCRIPT)


def package_module(module: dict, output_dir: Path) -> tuple[Path, int]:
    asset_name = f"{module['id']}-{module['versionCode']}.zip"
    asset_path = output_dir / asset_name
    if asset_path.exists():
        asset_path.unlink()

    with tempfile.TemporaryDirectory(prefix=f"mmrl-{module['id']}-", dir=str(output_dir)) as temp_dir:
        staging_dir = Path(temp_dir) / module["id"]
        staging_dir.mkdir(parents=True, exist_ok=True)

        copy_script = (
            f"src='{module['path']}'; dst='{staging_dir}'; "
            "find \"$src\" -mindepth 1 -maxdepth 1 "
            + "".join(f"! -name '{name}' " for name in sorted(EXCLUDED_FILES))
            + r"""-exec sh -c '
item="$1"
base="$(basename "$item")"
cp -aL "$item" "$2/$base"
' sh {} "$dst" \;"""
        )
        run(["su", "-c", copy_script])
        run(["su", "-c", f"chown -R {os.getuid()}:{os.getgid()} '{staging_dir}'"])

        write_installer_files(staging_dir)
        run(["chmod", "0755", str(staging_dir / "META-INF" / "com" / "google" / "android" / "update-binary")])
        run(["bash", "-lc", f"cd '{staging_dir}' && '{ZIP_BIN}' -qry -y '{asset_path}' ."])

    size = asset_path.stat().st_size
    return asset_path, size


def ensure_release() -> None:
    result = run([str(GH_BIN), "release", "view", RELEASE_TAG, "--repo", REPO_SLUG], check=False)
    if result.returncode == 0:
        return
    run(
        [
            str(GH_BIN),
            "release",
            "create",
            RELEASE_TAG,
            "--repo",
            REPO_SLUG,
            "--title",
            "Device Snapshot",
            "--notes",
            "Installable snapshots of the modules currently installed on the device.",
        ]
    )


def upload_assets(assets: list[Path]) -> None:
    if not assets:
        return
    cmd = [str(GH_BIN), "release", "upload", RELEASE_TAG, "--repo", REPO_SLUG, "--clobber"]
    cmd.extend(str(path) for path in assets)
    run(cmd)


def derive_support(update_json: str) -> str | None:
    if not update_json:
        return None
    if "raw.githubusercontent.com/" in update_json:
        trimmed = update_json.split("raw.githubusercontent.com/", 1)[1]
        owner_repo = trimmed.split("/", 2)[:2]
        if len(owner_repo) == 2:
            return f"https://github.com/{owner_repo[0]}/{owner_repo[1]}"
    if "github.com/" in update_json:
        parts = update_json.split("github.com/", 1)[1].split("/")
        if len(parts) >= 2:
            return f"https://github.com/{parts[0]}/{parts[1]}"
    return update_json


def module_to_feed_entry(module: dict, zip_size: int) -> dict:
    now = float(int(time.time()))
    asset_name = f"{module['id']}-{module['versionCode']}.zip"
    version_text = module["version"]
    description = module["description"]
    note = None
    if module["disabled"]:
        note = {
            "message": "This snapshot was taken from a currently disabled module on the device.",
        }
    entry = {
        "id": module["id"],
        "name": module["name"],
        "version": version_text,
        "versionCode": module["versionCode"],
        "author": module["author"],
        "description": description,
        "added": now,
        "support": derive_support(module["updateJson"]),
        "readme": derive_support(module["updateJson"]),
        "verified": False,
        "timestamp": now,
        "size": zip_size,
        "track": {
            "type": "ONLINE_JSON",
            "added": now,
            "source": PAGES_BASE,
            "antifeatures": None,
        },
        "versions": [
            {
                "timestamp": now,
                "version": version_text,
                "versionCode": module["versionCode"],
                "zipUrl": f"{RELEASE_BASE}/{asset_name}",
                "changelog": "",
                "size": zip_size,
            }
        ],
    }
    if note:
        entry["note"] = note
    return entry


def main() -> None:
    if shutil.which("su") is None:
        raise SystemExit("su is required")
    modules = list_modules()
    if not modules:
        raise SystemExit("No installed Magisk modules found")

    assets_dir = ROOT / "release-assets"
    assets_dir.mkdir(exist_ok=True)

    config = json.loads(CONFIG_PATH.read_text())
    config["description"] = (
        "MMRL feed snapshot of the Magisk modules currently installed on the device. "
        "Re-run the local sync script to refresh this list from live device state."
    )
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")

    packaged = []
    feed_modules = []
    for module in modules:
        asset_path, size = package_module(module, assets_dir)
        packaged.append(asset_path)
        feed_modules.append(module_to_feed_entry(module, size))

    ensure_release()
    upload_assets(packaged)

    device_manifest = {
        "generated_at": float(int(time.time())),
        "source": "device_snapshot",
        "modules": feed_modules,
    }
    DEVICE_MODULES_PATH.write_text(json.dumps(device_manifest, indent=2) + "\n")

    run([str(PYTHON_BIN), str(BUILD_SCRIPT)])

    print(f"modules={len(feed_modules)}")
    print(f"assets={len(packaged)}")


if __name__ == "__main__":
    main()
