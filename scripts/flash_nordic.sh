#!/usr/bin/env bash
# Flash both nRF5340 cores of the nRF7002-DK with the SignalHound scanner using the extracted J-Link tools.
# Needs USB write access to the J-Link probe (see docs/nordic-setup.md: udev rule or chmod).
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
J="${JLINK_EXE:-$HOME/dev/jlink/extracted/opt/SEGGER/JLink_V978/JLinkExe}"
B="${ZEPHYR_BUILD_DIR:-$HOME/dev/zephyr-sh}"
NET="${NET_HEX:-$B/build-net/zephyr/zephyr.hex}"
APP="${APP_HEX:-$B/build-app/zephyr/zephyr.hex}"
[ -x "$J" ] || { echo "JLinkExe not found at $J"; exit 1; }
[ -f "$NET" ] && [ -f "$APP" ] || { echo "hex files missing: $NET / $APP"; exit 1; }
tmp="$(mktemp -d)"
printf 'r\nh\nloadfile %s\nr\nq\n' "$NET" > "$tmp/net.jlink"
printf 'r\nh\nloadfile %s\nr\ng\nq\n' "$APP" > "$tmp/app.jlink"
run() { "$J" -device "$1" -if SWD -speed 4000 -autoconnect 1 -nogui 1 -CommanderScript "$2" 2>&1 | grep -E "Connecting|Cannot connect|Downloading|O.K.|Error|ERROR|failed|Verifying|Flash download" ; }
echo "== network core (BLE controller) =="; run nRF5340_xxAA_NET "$tmp/net.jlink"
echo "== application core (scanner) =="; run nRF5340_xxAA_APP "$tmp/app.jlink"
rm -rf "$tmp"
echo "== serial check (8 s) =="; timeout 8 cat /dev/ttyACM0 | head -10 || true
