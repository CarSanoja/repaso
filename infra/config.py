from dataclasses import dataclass

import aws_cdk as cdk

PROJECT = "repaso"
REGION = "us-east-1"
BOOTSTRAP_QUALIFIER = "repaso01"


@dataclass(frozen=True)
class DeployConfig:
    project: str
    region: str
    alert_email: str | None
    budget_limits_usd: tuple[int, ...]
    budget_alert_threshold_pct: int
    media_retention_days: int
    dlq_retention_days: int
    queue_visibility_minutes: int
    queue_max_receive: int
    log_retention_days: int
    bootstrap_qualifier: str

    @classmethod
    def from_app(cls, app: cdk.App) -> "DeployConfig":
        ctx = app.node.try_get_context
        return cls(
            project=ctx("project") or PROJECT,
            region=ctx("region") or REGION,
            alert_email=ctx("alert_email"),
            budget_limits_usd=cls._limits(ctx("budget_limits")),
            budget_alert_threshold_pct=int(ctx("budget_threshold") or 100),
            media_retention_days=int(ctx("media_retention_days") or 90),
            dlq_retention_days=int(ctx("dlq_retention_days") or 14),
            queue_visibility_minutes=int(ctx("queue_visibility_minutes") or 15),
            queue_max_receive=int(ctx("queue_max_receive") or 3),
            log_retention_days=int(ctx("log_retention_days") or 7),
            bootstrap_qualifier=ctx("@aws-cdk/core:bootstrapQualifier") or BOOTSTRAP_QUALIFIER,
        )

    @staticmethod
    def _limits(raw: object) -> tuple[int, ...]:
        if not raw:
            return (25, 40)
        if isinstance(raw, str):
            return tuple(int(x) for x in raw.split(",") if x.strip())
        return tuple(int(x) for x in raw)

    @property
    def synthesizer(self) -> cdk.DefaultStackSynthesizer:
        return cdk.DefaultStackSynthesizer(qualifier=self.bootstrap_qualifier)

    @property
    def env(self) -> cdk.Environment:
        return cdk.Environment(region=self.region)

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
