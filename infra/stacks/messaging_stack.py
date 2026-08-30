import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_sqs as sqs
from config import DeployConfig
from constructs import Construct


class MessagingStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, config: DeployConfig, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config

        self.bus = events.EventBus(self, "Bus", event_bus_name=config.bare())

        self.ingest_queue, self.ingest_dlq = self._queue_pair("ingest")
        self.tutor_queue, self.tutor_dlq = self._queue_pair("tutor")
        self.quality_queue, self.quality_dlq = self._queue_pair("quality")

        self._rule("IngestRule", ["material_uploaded"], self.ingest_queue)
        self._rule(
            "TutorRule",
            [
                "channel_message",
                "daily_session_due",
                "response_received",
                "escalation_resolved",
                "quarantine_resolved",
                "exam_announced",
            ],
            self.tutor_queue,
        )
        self._rule("QualityRule", ["daily_close"], self.quality_queue)

        scheduler.CfnScheduleGroup(self, "ScheduleGroup", name=config.bare())

        self.scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            role_name=config.resource("scheduler"),
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )
        self.bus.grant_put_events_to(self.scheduler_role)

    def _queue_pair(self, name: str) -> tuple[sqs.Queue, sqs.Queue]:
        dlq = sqs.Queue(
            self,
            f"{name.capitalize()}Dlq",
            queue_name=self.config.resource(name, "dlq"),
            retention_period=cdk.Duration.days(self.config.dlq_retention_days),
        )
        queue = sqs.Queue(
            self,
            f"{name.capitalize()}Queue",
            queue_name=self.config.resource(name),
            visibility_timeout=cdk.Duration.minutes(self.config.queue_visibility_minutes),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=self.config.queue_max_receive, queue=dlq
            ),
        )
        return queue, dlq

    def _rule(self, rule_id: str, detail_types: list[str], queue: sqs.Queue) -> None:
        events.Rule(
            self,
            rule_id,
            event_bus=self.bus,
            event_pattern=events.EventPattern(detail_type=detail_types),
            targets=[targets.SqsQueue(queue)],
        )
