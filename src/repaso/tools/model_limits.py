import time
from enum import StrEnum

from repaso.core.harness.budgets import CircuitBreaker
from repaso.core.telemetry.context import invocation_context

BREAKER_RECOVERY_SECONDS = 60
MESSAGE_SCOPE_KEY = "message_scope"
MESSAGE_QUOTA_TTL_SECONDS = 172800
SYSTEM_SCOPE = "system"
TRANSIENT_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelTimeoutException",
        "InternalServerException",
        "ModelNotReadyException",
        "TooManyRequestsException",
    }
)


class LimitReason(StrEnum):
    BREAKER_OPEN = "breaker_open"
    MESSAGE_CEILING = "message_ceiling"
    DAILY_CEILING = "daily_ceiling"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class ModelLimitReached(RuntimeError):
    def __init__(
        self, message: str, reason: LimitReason = LimitReason.PROVIDER_UNAVAILABLE
    ) -> None:
        super().__init__(message)
        self.reason = reason


def transient(error: BaseException) -> bool:
    response = getattr(error, "response", None)
    code = response.get("Error", {}).get("Code", "") if isinstance(response, dict) else ""
    return isinstance(error, TimeoutError | ConnectionError) or code in TRANSIENT_CODES


class ModelLimits:
    def __init__(self, settings, store, clock, quota=None):
        self.settings, self.store, self.clock = settings, store, clock
        self.quota = quota
        self.breakers = {}

    def before(self, role):
        breaker = self.breakers.setdefault(
            role, CircuitBreaker(recovery_steps=BREAKER_RECOVERY_SECONDS)
        )
        if not breaker.allow(int(time.monotonic())):
            raise ModelLimitReached(
                "model temporarily unavailable; retry after one minute",
                LimitReason.BREAKER_OPEN,
            )
        context = invocation_context.get() or {}
        self._reserve_message(context)
        if not self.store.reserve_budget(
            context.get("family_id", SYSTEM_SCOPE),
            self.clock.today().isoformat(),
            self.settings.daily_llm_budget_calls,
            self.settings.global_daily_llm_budget_calls,
        ):
            raise ModelLimitReached(
                "daily model allowance exhausted; pending work is preserved",
                LimitReason.DAILY_CEILING,
            )

    def _reserve_message(self, context):
        scope = context.get(MESSAGE_SCOPE_KEY)
        if self.quota is None or not scope:
            return
        expires = int(self.clock.now().timestamp()) + MESSAGE_QUOTA_TTL_SECONDS
        if not self.quota.reserve(scope, self.settings.message_llm_budget_calls, expires):
            raise ModelLimitReached(
                "this message already used its model allowance",
                LimitReason.MESSAGE_CEILING,
            )

    def after(self, role, success):
        breaker = self.breakers[role]
        if success:
            breaker.record_success(int(time.monotonic()))
        else:
            breaker.record_failure(int(time.monotonic()))
