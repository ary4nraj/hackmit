# Nordic nRF7002-DK setup (SignalHound scanner)

**Role:** the nRF5340 application core scans BLE continuously and prints the RSSI of every
advertisement whose local name equals `TARGET_NAME` ("Galaxy S25") as CSV over the J-Link VCOM
(`/dev/ttyACM0`, 115200). The nRF7002 Wi-Fi companion is unused: BLE RSSI is simpler and the
phone's nRF Connect app is a BLE advertiser.

## Firmware
`firmware/nordic/signalhound_scanner/` is a plain upstream-Zephyr app (no nRF Connect SDK needed):
active scanning, no duplicate filtering, fast scan window, name match, 1 Hz `SCAN` heartbeat, LED0
blink per target packet. Protocol: `signalhound/radio/scanner_protocol.py`.

Build environment (already provisioned in `~/dev/zephyr-sh`, ~700 MB): Zephyr v4.2.0 shallow clone +
modules `hal_nordic cmsis cmsis_6 mbedtls segger open-amp libmetal`, Zephyr SDK 0.17.4 (arm only),
`cmake<4` in `.venv`. Two images are required on nRF5340:

```bash
export PATH=$PWD/.venv/bin:$PATH ZEPHYR_BASE=~/dev/zephyr-sh/zephyr ZEPHYR_SDK_INSTALL_DIR=~/dev/zephyr-sh/zephyr-sdk-0.17.4 ZEPHYR_TOOLCHAIN_VARIANT=zephyr
cd ~/dev/zephyr-sh
west build -p always -b nrf7002dk/nrf5340/cpuapp -d build-app ~/dev/hackmit/firmware/nordic/signalhound_scanner
west build -p always -b nrf7002dk/nrf5340/cpunet -d build-net zephyr/samples/bluetooth/hci_ipc   # BLE controller
```
`prj.conf` sets `CONFIG_BOARD_ENABLE_CPUNET=y` so the app core releases the network core.
Gotchas hit: CMake 4 breaks Zephyr 4.2 (pin `cmake<4`); `open-amp`/`libmetal` modules are needed
for the HCI IPC link; upstream sysbuild does not auto-add `hci_ipc` for nrf7002dk.

## Flashing
Merged image: `firmware/nordic/signalhound_merged.hex` (app + net). Two options:
1. Drag-and-drop: copy the hex onto the `JLINK` USB mass-storage volume (no permissions needed).
2. `JLinkExe` (extracted from the SEGGER .deb into `~/dev/jlink/extracted`), one core at a time
   with `-device nRF5340_xxAA_NET` / `_APP`; needs write access to the USB device
   (`sudo cp ~/dev/jlink/extracted/etc/udev/rules.d/99-jlink.rules /etc/udev/rules.d/ && sudo udevadm control --reload` then replug).

## Lessons from bring-up (2026-09-19, all verified on the board)
- The console appears on the **second** J-Link VCOM (`/dev/ttyACM1` after the OB firmware update);
  `nordic_serial.py` now probes every SEGGER port for protocol lines, so no config is needed.
- `CONFIG_BT_EXT_ADV=y` in the app made `bt_le_scan_start` fail with -EIO because the upstream
  `hci_ipc` controller image is built without extended advertising. Removed; legacy scanning only.
- `bt_enable` needs the network core released: `CONFIG_BOARD_ENABLE_CPUNET=y` (deprecated name,
  still works in 4.2) and the `hci_ipc` image at 0x01000000.
- The J-Link MSD drag-and-drop does not work for this board (FAIL.TXT); use JLinkExe (installed by
  the nRF Connect VS Code extension pack, which also installed the udev rule).
- Debug without a console: `volatile` globals `dbg_stage/dbg_bt_err/dbg_scan_err` and the packet
  counters can be read with `JLinkExe ... mem32 <addr> 1` (addresses from `arm-zephyr-eabi-nm`).
- Two threads printing interleaved lines (`SCAN,SCAN,...`); printing is now under a mutex.
- Scan window == interval (continuous) to maximise target packet rate.

## Cable-free mode (RADIO_LINK=ble) — verified 2026-09-19 20:2x
The DK also advertises (non-connectable, 100–150 ms) a batch of its last 16 target RSSI samples with a
running index (manufacturer data, company 0xFFFF, `SH` magic). The laptop's own Bluetooth reads it
with `bleak` (`signalhound/radio/ble_link.py`), dedups by index, and feeds the same filter. Measured
~1.2 target samples/s end to end. BlueZ only surfaces ~1 advertisement update per 2 s per device
(passive scanning needs experimental BlueZ), which is why each advertisement carries a batch.
On the dog: DK + USB power bank, no laptop cable. Set `RADIO_LINK=ble` in `.env`. Serial output
keeps working when a cable is attached (`RADIO_LINK=serial`).

## Verify
`python scripts/radio_monitor.py --raw` should show `BOOT,0.1,...`, `SCAN,n,m` every second and
`TARGET,Galaxy S25,-6x,<addr>` lines while the phone advertises.
