"""Live RSSI monitor: python -m signalhound.radio.monitor [--raw]"""

import argparse
import sys
import time

from signalhound.config import Config
from signalhound.radio import make_radio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="echo every serial line")
    parser.add_argument("--log", default="", help="append CSV samples to this file")
    args = parser.parse_args()
    cfg = Config()
    log = open(args.log, "a") if args.log else None

    def on_line(line):
        if args.raw:
            print("  <", line, flush=True)
        if log and line.kind == "TARGET":
            log.write(f"{time.time():.3f},{line.name},{line.rssi}\n")
            log.flush()

    radio = make_radio(cfg, on_line).start()
    print(f"SignalHound radio monitor · target '{cfg.target_name}' · Ctrl+C to quit")
    try:
        while True:
            s = radio.snapshot()
            fr = "  n/a " if s["filtered"] is None else f"{s['filtered']:6.1f}"
            raw = " n/a" if s["raw"] is None else f"{s['raw']:4.0f}"
            others = " ".join(f"{k}:{v:.0f}" for k, v in list(s["others"].items())[:4])
            sys.stdout.write(
                f"\rTarget: {cfg.target_name} | RSSI: {raw} dBm | Filtered: {fr} dBm | "
                f"Samples: {s['samples']:2d}/{s['total']:<5d} | Status: {s['status']:9s} | "
                f"port={'ok' if s['connected'] else 'NONE'} hb={s['heartbeat_age']} | {others[:40]:40s}"
            )
            sys.stdout.flush()
            time.sleep(0.25)
    except KeyboardInterrupt:
        print()
    finally:
        radio.stop()
        if log:
            log.close()


if __name__ == "__main__":
    main()
