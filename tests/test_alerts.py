import alerts

def test_build_schedule_full():
    sched = alerts.build_schedule(10000.0, 0.0)
    assert [t for t, _ in sched] == [10000.0 - 1800, 10000.0 - 900, 10000.0 - 300, 10000.0 - 60]
    assert "30 mins" in sched[0][1] and "1 MIN" in sched[-1][1]

def test_build_schedule_drops_past_alerts():
    sched = alerts.build_schedule(10000.0, 10000.0 - 200)  # inside T-5min
    assert [t for t, _ in sched] == [10000.0 - 60]

def test_imessage_cmd_escapes_quotes():
    cmd = alerts.imessage_cmd("+15551234567", 'say "hi"')
    assert cmd[0] == "osascript" and '\\"hi\\"' in cmd[-1]
