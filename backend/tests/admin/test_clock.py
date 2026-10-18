from datetime import timedelta, timezone

from backend.admin.security.clock import Clock, FakeClock, SystemClock


def test_both_implementations_satisfy_the_protocol():
    assert isinstance(SystemClock(), Clock)
    assert isinstance(FakeClock(), Clock)


def test_system_clock_is_utc_and_current():
    clock = SystemClock()
    assert clock.now().tzinfo == timezone.utc
    assert abs(clock.now().timestamp() - clock.time()) < 5


def test_fake_clock_moves_only_when_told():
    clock = FakeClock(1000)
    assert clock.time() == 1000
    clock.advance(30)
    assert clock.time() == 1030
    clock.advance_delta(timedelta(minutes=1))
    assert clock.time() == 1090
    clock.set(5)
    assert clock.now().timestamp() == 5
    assert clock.now().tzinfo == timezone.utc
