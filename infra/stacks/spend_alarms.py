import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cloudwatch
from config import DeployConfig

NAMESPACE = "repaso"
SPEND_METRIC = "llm.estimated_usd"
DAILY_CEILING_METRIC = "spend.daily_ceiling.tripped"
MESSAGE_CEILING_METRIC = "spend.message_ceiling.tripped"
RATE_LIMITED_METRIC = "throttle.rate_limited.refused"
UNKNOWN_CHAT_METRIC = "throttle.unknown_chat_exhausted.refused"

HOUR = cdk.Duration.hours(1)
DAY = cdk.Duration.days(1)
WINDOW = cdk.Duration.minutes(5)
ABUSE_WINDOW = cdk.Duration.minutes(15)
ANY = 0


def metric(name: str, period: cdk.Duration, label: str) -> cloudwatch.Metric:
    return cloudwatch.Metric(
        namespace=NAMESPACE,
        metric_name=name,
        period=period,
        statistic="Sum",
        label=label,
    )


def specs(config: DeployConfig) -> list[tuple[str, tuple[str, ...], cloudwatch.IMetric, float]]:
    return [
        (
            "ModelSpendHourAlarm",
            ("model", "spend", "hour"),
            metric(SPEND_METRIC, HOUR, "estimated model spend, hour"),
            config.hourly_model_spend_usd,
        ),
        (
            "ModelSpendDayAlarm",
            ("model", "spend", "day"),
            metric(SPEND_METRIC, DAY, "estimated model spend, day"),
            config.daily_model_spend_usd,
        ),
        (
            "DailyCeilingAlarm",
            ("model", "daily", "ceiling"),
            metric(DAILY_CEILING_METRIC, WINDOW, "families stopped by the daily ceiling"),
            ANY,
        ),
        (
            "MessageCeilingAlarm",
            ("model", "message", "ceiling"),
            metric(MESSAGE_CEILING_METRIC, WINDOW, "messages stopped by their own ceiling"),
            ANY,
        ),
        (
            "RateLimitedChatsAlarm",
            ("chats", "rate", "limited"),
            metric(RATE_LIMITED_METRIC, ABUSE_WINDOW, "chats refused for rate"),
            config.refused_chats_per_window,
        ),
        (
            "UnknownChatsAlarm",
            ("chats", "unknown", "exhausted"),
            metric(UNKNOWN_CHAT_METRIC, ABUSE_WINDOW, "unknown chats that spent their day"),
            config.refused_chats_per_window,
        ),
    ]
