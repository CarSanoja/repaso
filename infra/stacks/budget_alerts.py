from aws_cdk import aws_budgets as budgets
from config import DeployConfig
from constructs import Construct

COST = "COST"
MONTHLY = "MONTHLY"
ACTUAL = "ACTUAL"
GREATER_THAN = "GREATER_THAN"
USD = "USD"
EMAIL = "EMAIL"


def add_budget_alerts(scope: Construct, config: DeployConfig) -> list[budgets.CfnBudget]:
    if not config.alert_email:
        return []
    return [_budget(scope, config, limit) for limit in config.budget_limits_usd]


def _budget(scope: Construct, config: DeployConfig, limit: int) -> budgets.CfnBudget:
    return budgets.CfnBudget(
        scope,
        f"Budget{limit}",
        budget=budgets.CfnBudget.BudgetDataProperty(
            budget_name=config.resource(str(limit)),
            budget_type=COST,
            time_unit=MONTHLY,
            budget_limit=budgets.CfnBudget.SpendProperty(amount=limit, unit=USD),
        ),
        notifications_with_subscribers=[_notification(config)],
    )


def _notification(config: DeployConfig) -> budgets.CfnBudget.NotificationWithSubscribersProperty:
    return budgets.CfnBudget.NotificationWithSubscribersProperty(
        notification=budgets.CfnBudget.NotificationProperty(
            notification_type=ACTUAL,
            comparison_operator=GREATER_THAN,
            threshold=config.budget_alert_threshold_pct,
        ),
        subscribers=[
            budgets.CfnBudget.SubscriberProperty(
                subscription_type=EMAIL, address=config.alert_email
            )
        ],
    )
