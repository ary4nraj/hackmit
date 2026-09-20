#!/usr/bin/env bash
# Join the Go2's Wi-Fi AP (name changes every boot: Go2_61034_<random>) WITHOUT taking the default
# route, so internet keeps flowing over a second interface (phone USB tethering -> usb0, or Ethernet).
#   ./scripts/net_go2.sh          connect (password from .env GO2_WIFI_PASSWORD)
#   ./scripts/net_go2.sh off      back to the normal Wi-Fi
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$root"
serial="${GO2_SERIAL:-61034}"
if [ "${1:-}" = "test" ]; then
  # Self-contained probe: switch to the robot, log diagnostics, switch back automatically.
  log="data/logs/netprobe-$(date +%H%M%S).log"; mkdir -p data/logs
  { "$0"; sleep 3; echo "--- routes ---"; ip route | grep default; ip route get 1.1.1.1 | head -1; echo "--- dns ---"; resolvectl status 2>/dev/null | grep -E "^Link|DNS Servers|DefaultRoute|Current DNS" | head -16
    T="$(ip -br link | awk '/^enx/{print $1; exit}')"
    echo -n "ip-only https via tether: "; curl -4 -s -o /dev/null -m 8 --interface "$T" -w "%{http_code}\n" https://1.1.1.1/ || echo FAIL
    echo -n "ip-only https default route: "; curl -4 -s -o /dev/null -m 8 -w "%{http_code}\n" https://1.1.1.1/ || echo FAIL
    echo -n "resolvectl query: "; resolvectl query api.anthropic.com 2>&1 | head -2 | tr '\n' ' '; echo
    echo -n "dig @1.1.1.1 via tether: "; dig +short +time=3 @1.1.1.1 api.anthropic.com 2>&1 | head -1
    echo -n "plain curl: "; curl -4 -s -o /dev/null -m 8 -w "%{http_code}\n" https://api.anthropic.com/ || echo FAIL
    echo -n "curl via tether: "; curl -4 -s -o /dev/null -m 8 --interface "$(ip -br link | awk '/^enx/{print $1; exit}')" -w "%{http_code}\n" https://api.anthropic.com/ || echo FAIL
    echo -n "dns lookup: "; getent hosts api.anthropic.com | head -1 || echo FAIL
    echo -n "robot: "; ping -c 1 -W 2 192.168.12.1 >/dev/null && echo ok || echo unreachable
    sleep "${PROBE_HOLD:-10}"; "$0" off; } > "$log" 2>&1
  echo "$log"; exit 0
fi
if [ "${1:-}" = "off" ]; then
  for c in $(nmcli -t -f NAME con show | grep "^Go2_"); do nmcli con down "$c" >/dev/null 2>&1 || true; done
  nmcli con modify "${NORMAL_WIFI:-HackMIT.2026}" connection.autoconnect yes >/dev/null 2>&1 || true
  nmcli con up id "${NORMAL_WIFI:-HackMIT.2026}" >/dev/null 2>&1 || true
  nmcli -t -f NAME,DEVICE con show --active | head -1; exit 0
fi
# Re-apply the tether profile so its DNS settings (set below on first run) are live.
for c in $(nmcli -t -f NAME,TYPE con show --active | grep ":802-3-ethernet" | cut -d: -f1); do
  nmcli con modify "$c" ipv4.dns-priority 10 ipv4.dns "1.1.1.1 8.8.8.8" ipv4.ignore-auto-dns yes ipv6.dns-priority 10 >/dev/null 2>&1 || true
  nmcli con up "$c" >/dev/null 2>&1 || true
done
pw="$(.venv/bin/python -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('GO2_WIFI_PASSWORD',''))")"
[ -n "$pw" ] || { echo "GO2_WIFI_PASSWORD missing in .env"; exit 1; }
for c in $(nmcli -t -f NAME con show | grep "^Go2_"); do nmcli con delete "$c" >/dev/null 2>&1 || true; done
nmcli dev wifi rescan >/dev/null 2>&1 || true; sleep 4
ssid="$(nmcli -t -f SSID,SIGNAL dev wifi list | grep "^Go2_${serial}" | sort -t: -k2 -rn | head -1 | cut -d: -f1)"
[ -n "$ssid" ] || { echo "no Go2_${serial}_* AP visible; is the robot on?"; exit 1; }
echo "joining $ssid"
nmcli con add type wifi ifname wlp1s0 con-name "$ssid" ssid "$ssid" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$pw" \
  ipv4.never-default yes ipv6.never-default yes ipv4.ignore-auto-dns yes ipv6.ignore-auto-dns yes \
  ipv4.dns-priority 500 connection.autoconnect no >/dev/null
# The tether (or Ethernet) must win DNS once Wi-Fi is on the robot.
for c in $(nmcli -t -f NAME,TYPE con show | grep ":802-3-ethernet" | cut -d: -f1); do nmcli con modify "$c" ipv4.dns-priority 10 ipv4.dns "1.1.1.1 8.8.8.8" >/dev/null 2>&1 || true; done
nmcli con up "$ssid" | tail -1
sleep 2
echo -n "robot:    "; ping -c 1 -W 2 192.168.12.1 >/dev/null 2>&1 && echo "reachable (192.168.12.1)" || echo "NOT reachable"
echo -n "internet: "; curl -4 -s -o /dev/null -m 8 -w "%{http_code}" https://api.anthropic.com/ >/dev/null 2>&1 && echo "OK ($(ip route | awk '/^default/{print $5; exit}'))" || echo "NONE — check the USB tether (phone hotspot on, cable in) and DNS: resolvectl status"
