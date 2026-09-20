def make_radio(cfg, on_line=None):
    """RADIO_LINK=serial (USB cable to the DK) or ble (the DK rebroadcasts; laptop Bluetooth reads it)."""
    if getattr(cfg, "radio_link", "serial") == "ble":
        from signalhound.radio.ble_link import BleLink

        return BleLink(cfg, on_line)
    from signalhound.radio.nordic_serial import NordicSerial

    return NordicSerial(cfg, on_line)
