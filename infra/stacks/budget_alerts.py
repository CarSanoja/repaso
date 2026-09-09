import aws_cdk as cdk
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from config import COST_TAG, DeployConfig
from constructs import Construct

BUDGETS_SERVICE = "budgets.amazonaws.com"
ACTUAL = "ACTUAL"
FORECASTED = "FORECASTED"
PERCENTAGE = "PERCENTAGE"
FORECAST_THRESHOLD = 100

NO_ADDRESS = (
    "No alert_email in context. Budgets and alarms publish to the alerts topic and "
    "the topic has no subscription, so nothing reaches a person."
)
TAG_NOTE = (
    f"Budgets filter on cost allocation tag '{COST_TAG}'. Until that tag is activated "
    "in Billing the filtered spend reads as zero and no budget notification fires."
)


def alerts_topic(scope: Construct, config: DeployConfig) -> sns.Topic:
    topic = sns.Topic(scope, "Alerts", topic_name=config.resource("alerts"))
    topic.add_to_resource_policy(
        iam.PolicyStatement(
            actions=["SNS:Publish"],
            principals=[iam.ServicePrincipal(BUDGETS_SERVICE)],
            resources=[topic.topic_arn],
        )
    )
    if config.alert_email:
        topic.add_subscription(subscriptions.EmailSubscription(config.alert_email))
    else:
        cdk.Annotations.of(scope).add_warning(NO_ADDRESS)
    return topic


def _notification(kind: str, threshold: float, topic: sns.Topic):
    return budgets.CfnBudget.NotificationWithSubscribersProperty(
        notification=budgets.CfnBudget.NotificationProperty(
            notification_type=kind,
            comparison_operator="GREATER_THAN",
            threshold=threshold,
            threshold_type=PERCENTAGE,
        ),
        subscribers=[
            budgets.CfnBudget.SubscriberProperty(
                subscription_type="SNS", address=topic.topic_arn
            )
        ],
    )


def monthly_budgets(
    scope: Construct, config: DeployConfig, topic: sns.Topic
) -> list[budgets.CfnBudget]:
    cdk.Annotations.of(scope).add_info(TAG_NOTE)
    created = []
    for limit in config.budget_limits_usd:
        notifications = [
            _notification(ACTUAL, threshold, topic)
            for threshold in config.budget_alert_thresholds_pct
        ]
        notifications.append(_notification(FORECASTED, FORECAST_THRESHOLD, topic))
        created.append(
            budgets.CfnBudget(
                scope,
                f"Budget{limit}",
                budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_name=config.resource(str(limit)),
                    budget_type="COST",
                    time_unit="MONTHLY",
                    budget_limit=budgets.CfnBudget.SpendProperty(amount=limit, unit="USD"),
                    cost_filters=config.cost_filter,
                ),
                notifications_with_subscribers=notifications,
            )
        )
    return created
