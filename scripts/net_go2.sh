#!/usr/bin/env bash
# Join the Go2's Wi-Fi AP (name changes every boot: Go2_61034_<random>) WITHOUT taking the default
# route, so internet keeps flowing over a second interface (phone USB tethering -> usb0, or Ethernet).
#   ./scripts/net_go2.sh          connect (password from .env GO2_WIFI_PASSWORD)
#   ./scripts/net_go2.sh off      back to the normal Wi-Fi
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$root"
serial="${GO2_SERIAL:-61034}"
if [ "${1:-}" = "off" ]; then
  for c in $(nmcli -t -f NAME con show | grep "^Go2_"); do nmcli con down "$c" >/dev/null 2>&1 || true; done
  nmcli con up id "${NORMAL_WIFI:-HackMIT.2026}" >/dev/null 2>&1 || true
  nmcli -t -f NAME,DEVICE con show --active | head -1; exit 0
fi
pw="$(.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('GO2_WIFI_PASSWORD',''))")"
[ -n "$pw" ] || { echo "GO2_WIFI_PASSWORD missing in .env"; exit 1; }
for c in $(nmcli -t -f NAME con show | grep "^Go2_"); do nmcli con delete "$c" >/dev/null 2>&1 || true; done
nmcli dev wifi rescan >/dev/null 2>&1 || true; sleep 4
ssid="$(nmcli -t -f SSID,SIGNAL dev wifi list | grep "^Go2_${serial}" | sort -t: -k2 -rn | head -1 | cut -d: -f1)"
[ -n "$ssid" ] || { echo "no Go2_${serial}_* AP visible; is the robot on?"; exit 1; }
echo "joining $ssid"
nmcli con add type wifi ifname wlp1s0 con-name "$ssid" ssid "$ssid" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$pw" \
  ipv4.never-default yes ipv6.never-default yes connection.autoconnect no >/dev/null
nmcli con up "$ssid" | tail -1
sleep 2
echo -n "robot:    "; ping -c 1 -W 2 192.168.12.1 >/dev/null 2>&1 && echo "reachable (192.168.12.1)" || echo "NOT reachable"
echo -n "internet: "; curl -s -o /dev/null -m 6 -w "%{http_code}" https://api.anthropic.com/ >/dev/null 2>&1 && echo "OK ($(ip route | awk '/^default/{print $5; exit}'))" || echo "NONE — enable USB tethering on the phone (Settings > Connections > Mobile Hotspot and Tethering > USB tethering) and plug it in"
