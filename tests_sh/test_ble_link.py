import struct
from signalhound.radio.ble_link import parse_batch


def payload(idx, vals, age=1, seq=7):
    return b"SH" + struct.pack("<BHBB", seq, idx, len(vals), age) + struct.pack(f"<{len(vals)}b", *vals)


def test_batch_dedup_and_order():
    # newest first on the wire: idx 10 -> samples 10,9,8,...
    new, idx, age = parse_batch(payload(10, [-60, -61, -62, -63, -64, -65]), None)
    assert idx == 10 and age == 1 and new == [-64, -63, -62, -61, -60]  # first contact: last 5, oldest first
    new, idx, _ = parse_batch(payload(13, [-50, -51, -52, -60, -61]), 10)
    assert new == [-52, -51, -50]  # exactly the 3 samples newer than idx 10
    new, _, _ = parse_batch(payload(13, [-50, -51, -52]), 13)
    assert new == []
    assert parse_batch(b"XX", None) is None
    new, _, age = parse_batch(payload(0, [], age=255), None)
    assert new == [] and age == 255
