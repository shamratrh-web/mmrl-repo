# MMRL Device Snapshot Feed

This repository publishes installable snapshot zips for the Magisk modules currently installed on the device.

Add this repository to MMRL with:

- `https://shamratrh-web.github.io/mmrl-repo/json/modules.json`

How it works:

- Pages serves the repository metadata and `modules.json`.
- GitHub Releases stores the generated module zip payloads.
- The local sync script reads `/data/adb/modules`, packages clean Magisk-installable snapshots, uploads release assets, and regenerates the feed.

To refresh the feed from the device again, run:

- `python /data/data/com.termux/files/home/mmrl-repo/scripts/sync_device_snapshot.py`
