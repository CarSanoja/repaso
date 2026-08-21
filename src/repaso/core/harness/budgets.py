CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_RECOVERY_STEPS = 5
DEFAULT_MAX_ATTEMPTS = 2


class DailyBudget:
    def __init__(self, limit_calls: int, spent: int = 0) -> None:
        if limit_calls < 0:
            raise ValueError("limit_calls must not be negative")
        if not 0 <= spent <= limit_calls:
            raise ValueError("spent must be between 0 and limit_calls")
        self.limit_calls = limit_calls
        self.spent = spent

    def try_spend(self, n: int = 1) -> bool:
        if n < 1:
            raise ValueError("n must be positive")
        if self.spent + n > self.limit_calls:
            return False
        self.spent += n
        return True

    def remaining(self) -> int:
        return self.limit_calls - self.spent

    def exhausted(self) -> bool:
        return self.remaining() <= 0

    def snapshot(self) -> dict[str, int]:
        return {"limit": self.limit_calls, "spent": self.spent, "remaining": self.remaining()}


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_steps: int = DEFAULT_RECOVERY_STEPS,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if recovery_steps < 1:
            raise ValueError("recovery_steps must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_steps = recovery_steps
        self.consecutive_failures = 0
        self.opened_step: int | None = None
        self.current_state = CLOSED

    def record_failure(self, step: int) -> None:
        self.consecutive_failures += 1
        if self.current_state == HALF_OPEN or self.consecutive_failures >= self.failure_threshold:
            self.opened_step = step
            self.current_state = OPEN

    def record_success(self, step: int) -> None:
        if self.current_state == OPEN and not self.recovered(step):
            return
        self.consecutive_failures = 0
        self.opened_step = None
        self.current_state = CLOSED

    def allow(self, step: int) -> bool:
        if self.current_state == OPEN and self.recovered(step):
            self.current_state = HALF_OPEN
        return self.current_state != OPEN

    def recovered(self, step: int) -> bool:
        return self.opened_step is not None and step >= self.opened_step + self.recovery_steps

    def state(self) -> str:
        return self.current_state

    def snapshot(self) -> dict[str, int | str | None]:
        return {
            "state": self.current_state,
            "consecutive_failures": self.consecutive_failures,
            "opened_step": self.opened_step,
        }


class BoundedAttempts:
    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> None:
        if max_attempts < 0:
            raise ValueError("max_attempts must not be negative")
        self.max_attempts = max_attempts
        self.used = 0

    def try_attempt(self) -> bool:
        if self.used >= self.max_attempts:
            return False
        self.used += 1
        return True

    def attempts_used(self) -> int:
        return self.used

    def remaining(self) -> int:
        return self.max_attempts - self.used

    def exhausted(self) -> bool:
        return self.remaining() <= 0

    def snapshot(self) -> dict[str, int]:
        return {"max_attempts": self.max_attempts, "used": self.used, "remaining": self.remaining()}
