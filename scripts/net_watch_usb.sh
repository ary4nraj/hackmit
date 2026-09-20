#!/usr/bin/env bash
# Wait for a USB-tethered phone interface, then test internet THROUGH IT (without touching the
# current default route). Prints a verdict. Usage: ./scripts/net_watch_usb.sh [timeout_s]
t="${1:-180}"
for _ in $(seq 1 "$t"); do dev=$(ip -br link | awk '/^(enx|eth[0-9]|usb)/{print $1; exit}'); [ -n "$dev" ] && break; sleep 1; done
[ -n "$dev" ] || { echo "no USB network interface appeared in ${t}s"; exit 1; }
echo "interface: $dev"
for _ in $(seq 1 30); do ip -4 addr show "$dev" | grep -q "inet " && break; sleep 1; done
ip -br addr show "$dev"; gw=$(ip route show dev "$dev" | awk '/via/{print $3; exit}'); ip route show dev "$dev" | head -3
echo -n "gateway ${gw:-?}: "; [ -n "$gw" ] && ping -c 1 -W 2 -I "$dev" "$gw" >/dev/null 2>&1 && echo ok || echo "NO"
echo -n "internet via $dev: "; curl -s -o /dev/null -m 8 --interface "$dev" -w "HTTP %{http_code}\n" https://api.anthropic.com/ || echo "NONE (phone hotspot has no data? cellular on? Personal Hotspot on?)"
