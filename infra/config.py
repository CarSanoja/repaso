from dataclasses import dataclass

import aws_cdk as cdk
from retention import DeploymentMode

PROJECT = "repaso"
REGION = "us-east-1"
BOOTSTRAP_QUALIFIER = "repaso01"
COST_TAG = "project"
DEFAULT_BUDGET_THRESHOLDS = (50, 80, 100)


@dataclass(frozen=True)
class DeployConfig:
    project: str
    region: str
    alert_email: str | None
    budget_limits_usd: tuple[int, ...]
    budget_alert_thresholds_pct: tuple[int, ...]
    media_retention_days: int
    dlq_retention_days: int
    queue_visibility_minutes: int
    queue_max_receive: int
    queue_stall_minutes: int
    log_retention_days: int
    hourly_model_spend_usd: float
    daily_model_spend_usd: float
    refused_chats_per_window: int
    webhook_rate_limit: int
    webhook_burst_limit: int
    webhook_reserved_concurrency: int
    worker_reserved_concurrency: int
    worker_queue_concurrency: int
    scheduler_reserved_concurrency: int
    bootstrap_qualifier: str
    mode: DeploymentMode

    @classmethod
    def from_app(cls, app: cdk.App) -> "DeployConfig":
        ctx = app.node.try_get_context
        return cls(
            project=ctx("project") or PROJECT,
            region=ctx("region") or REGION,
            alert_email=ctx("alert_email"),
            budget_limits_usd=cls._ints(ctx("budget_limits"), (25, 40)),
            budget_alert_thresholds_pct=cls._ints(
                ctx("budget_thresholds"), DEFAULT_BUDGET_THRESHOLDS
            ),
            media_retention_days=int(ctx("media_retention_days") or 90),
            dlq_retention_days=int(ctx("dlq_retention_days") or 14),
            queue_visibility_minutes=int(ctx("queue_visibility_minutes") or 15),
            queue_max_receive=int(ctx("queue_max_receive") or 3),
            queue_stall_minutes=int(ctx("queue_stall_minutes") or 30),
            log_retention_days=int(ctx("log_retention_days") or 7),
            hourly_model_spend_usd=float(ctx("hourly_model_spend_usd") or 2),
            daily_model_spend_usd=float(ctx("daily_model_spend_usd") or 10),
            refused_chats_per_window=int(ctx("refused_chats_per_window") or 20),
            webhook_rate_limit=int(ctx("webhook_rate_limit") or 20),
            webhook_burst_limit=int(ctx("webhook_burst_limit") or 40),
            webhook_reserved_concurrency=int(ctx("webhook_reserved_concurrency") or 10),
            worker_reserved_concurrency=int(ctx("worker_reserved_concurrency") or 15),
            worker_queue_concurrency=int(ctx("worker_queue_concurrency") or 4),
            scheduler_reserved_concurrency=int(ctx("scheduler_reserved_concurrency") or 5),
            bootstrap_qualifier=ctx("@aws-cdk/core:bootstrapQualifier") or BOOTSTRAP_QUALIFIER,
            mode=DeploymentMode.parse(ctx("deployment_mode")),
        )

    @staticmethod
    def _ints(raw: object, fallback: tuple[int, ...]) -> tuple[int, ...]:
        if not raw:
            return fallback
        if isinstance(raw, str):
            return tuple(int(x) for x in raw.split(",") if x.strip())
        return tuple(int(x) for x in raw)

    @property
    def tags(self) -> dict[str, str]:
        return {"project": self.project, "managed-by": "cdk", "deployment-mode": self.mode.value}

    @property
    def synthesizer(self) -> cdk.DefaultStackSynthesizer:
        return cdk.DefaultStackSynthesizer(qualifier=self.bootstrap_qualifier)

    @property
    def env(self) -> cdk.Environment:
        return cdk.Environment(region=self.region)

    @property
    def cost_filter(self) -> dict[str, list[str]]:
        return {"TagKeyValue": [f"user:{COST_TAG}${self.project}"]}

    def stack(self, name: str) -> str:
        return f"{self.project}-{name}"

    def resource(self, *parts: str) -> str:
        return "-".join((self.project, *parts))

    def secret(self, name: str) -> str:
        return f"{self.project}/{name}"

    def parameter(self, *parts: str) -> str:
        return "/" + "/".join((self.project, *parts))

    def bare(self) -> str:
        return self.project
