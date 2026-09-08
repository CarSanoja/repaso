import aws_cdk as cdk
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from config import DeployConfig
from constructs import Construct

TLS_FLOOR = 1.2


class FoundationStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, config: DeployConfig, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config

        self.key = kms.Key(self, "RepasoKey", alias=config.bare(), enable_key_rotation=True)

        self.media_bucket = s3.Bucket(
            self,
            "MediaBucket",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            minimum_tls_version=TLS_FLOOR,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(config.media_retention_days)
                )
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        self.curriculum_bucket = s3.Bucket(
            self,
            "CurriculumBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            minimum_tls_version=TLS_FLOOR,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=config.bare(),
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.key,
            time_to_live_attribute="expires_at",
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.table.add_global_secondary_index(
            index_name="gsi1",
            partition_key=dynamodb.Attribute(name="gsi1pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="gsi1sk", type=dynamodb.AttributeType.STRING),
        )

        self.telegram_secret = secretsmanager.Secret(
            self, "TelegramSecret", secret_name=config.secret("telegram")
        )
        self.judge_secret = secretsmanager.Secret(
            self, "JudgeSecret", secret_name=config.secret("judge")
        )
        self.invite_codes_secret = secretsmanager.Secret(
            self,
            "InviteCodesSecret",
            secret_name=config.secret("pilot-invite-codes"),
            encryption_key=self.key,
        )

        alert_email = config.alert_email
        if alert_email:
            for limit in config.budget_limits_usd:
                budgets.CfnBudget(
                    self,
                    f"Budget{limit}",
                    budget=budgets.CfnBudget.BudgetDataProperty(
                        budget_name=config.resource(str(limit)),
                        budget_type="COST",
                        time_unit="MONTHLY",
                        budget_limit=budgets.CfnBudget.SpendProperty(amount=limit, unit="USD"),
                    ),
                    notifications_with_subscribers=[
                        budgets.CfnBudget.NotificationWithSubscribersProperty(
                            notification=budgets.CfnBudget.NotificationProperty(
                                notification_type="ACTUAL",
                                comparison_operator="GREATER_THAN",
                                threshold=config.budget_alert_threshold_pct,
                            ),
                            subscribers=[
                                budgets.CfnBudget.SubscriberProperty(
                                    subscription_type="EMAIL", address=alert_email
                                )
                            ],
                        )
                    ],
                )
