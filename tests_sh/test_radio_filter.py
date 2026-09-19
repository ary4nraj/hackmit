from signalhound.radio.filter import RssiFilter
from signalhound.radio.scanner_protocol import parse_line


def test_median_rejects_spike():
    now = [100.0]
    f = RssiFilter(window=5, min_samples=3, alpha=1.0, clock=lambda: now[0])
    for r in (-70, -69, -95, -71, -70):
        f.add(r)
    assert f.median() == -70
    assert abs(f.get_filtered_rssi() - -70) < 1e-9
    assert f.status() == "tracking" and f.ready()
    now[0] += 10
    assert f.status() == "lost" and not f.ready()


def test_parse_lines():
    t = parse_line("TARGET,Galaxy S25,-63,5C:2E:59:11:22:33 (random)\r\n")
    assert t.kind == "TARGET" and t.name == "Galaxy S25" and t.rssi == -63
    assert parse_line("SCAN,120,7").extra == (120, 7)
    assert parse_line("RSSI,-61").rssi == -61
    assert parse_line("garbage") is None and parse_line("TARGET,x,notanumber") is None
