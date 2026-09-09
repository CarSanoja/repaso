from enum import StrEnum

import aws_cdk as cdk

EPHEMERAL_KEY_PENDING_DAYS = 7
DURABLE_SURVIVORS = ("kms key", "media bucket", "state table")


class DeploymentMode(StrEnum):
    DURABLE = "durable"
    EPHEMERAL = "ephemeral"

    @classmethod
    def parse(cls, raw: object) -> "DeploymentMode":
        if raw is None or not str(raw).strip():
            return cls.DURABLE
        text = str(raw).strip().lower()
        known = tuple(mode.value for mode in cls)
        if text not in known:
            raise ValueError(f"deployment_mode must be one of {', '.join(known)}, not {text!r}")
        return cls(text)

    @property
    def keeps_data(self) -> bool:
        return self is DeploymentMode.DURABLE

    @property
    def data_removal_policy(self) -> cdk.RemovalPolicy:
        return cdk.RemovalPolicy.RETAIN if self.keeps_data else cdk.RemovalPolicy.DESTROY

    @property
    def empties_buckets(self) -> bool:
        return not self.keeps_data

    @property
    def key_pending_window(self) -> cdk.Duration | None:
        if self.keeps_data:
            return None
        return cdk.Duration.days(EPHEMERAL_KEY_PENDING_DAYS)

    @property
    def survivors(self) -> str:
        return ", ".join(DURABLE_SURVIVORS) if self.keeps_data else "none"
