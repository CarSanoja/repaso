import time

from repaso.core.harness.budgets import CircuitBreaker
from repaso.core.telemetry.context import invocation_context


class ModelLimitReached(RuntimeError):
    pass


class ModelLimits:
    def __init__(self, settings, store, clock):
        self.settings, self.store, self.clock = settings, store, clock
        self.breakers = {}

    def before(self, role):
        breaker = self.breakers.setdefault(role, CircuitBreaker(recovery_steps=60))
        if not breaker.allow(int(time.monotonic())):
            raise ModelLimitReached("model temporarily unavailable; retry after one minute")
        scope = (invocation_context.get() or {}).get("family_id", "system")
        if not self.store.reserve_budget(
            scope,
            self.clock.today().isoformat(),
            self.settings.daily_llm_budget_calls,
            self.settings.global_daily_llm_budget_calls,
        ):
            raise ModelLimitReached("daily model allowance exhausted; pending work is preserved")

    def after(self, role, success):
        breaker = self.breakers[role]
        if success:
            breaker.record_success(int(time.monotonic()))
        else:
            breaker.record_failure(int(time.monotonic()))
