import timesync

def test_parse_server_epoch():
    # RFC 7231 Date header
    assert timesync.parse_server_epoch("Tue, 14 Jul 2026 12:00:00 GMT") == 1784030400.0

def test_corrected_now_applies_offset():
    import time
    off = 5.0
    assert abs(timesync.corrected_now(off) - (time.time() + 5.0)) < 0.5
