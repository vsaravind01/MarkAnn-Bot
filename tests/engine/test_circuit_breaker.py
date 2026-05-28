import time

from engine.circuit_breaker import CircuitBreaker, CircuitState


def test_initial_state_is_closed():
    cb = CircuitBreaker(failure_threshold=3, hold_off=1.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3, hold_off=60.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_attempt() is False


def test_success_resets_to_closed():
    cb = CircuitBreaker(failure_threshold=2, hold_off=60.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    cb._opened_at = time.monotonic() - 61.0
    assert cb.can_attempt() is True  # transitions to HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_half_open_failure_reopens():
    cb = CircuitBreaker(failure_threshold=2, hold_off=0.01)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.02)
    assert cb.can_attempt() is True  # → HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_failure_count_resets_on_success():
    cb = CircuitBreaker(failure_threshold=5, hold_off=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb._failure_count == 0
    assert cb.state == CircuitState.CLOSED
