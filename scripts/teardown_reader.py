import json

from teardown_plan import PROJECT

LIVE_STACKS = (
    "CREATE_COMPLETE",
    "CREATE_FAILED",
    "CREATE_IN_PROGRESS",
    "DELETE_FAILED",
    "IMPORT_COMPLETE",
    "IMPORT_ROLLBACK_COMPLETE",
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
    "UPDATE_COMPLETE",
    "UPDATE_FAILED",
    "UPDATE_ROLLBACK_COMPLETE",
    "UPDATE_ROLLBACK_FAILED",
)
RETAIN = "Retain"
LOG_PREFIXES = ("/aws/lambda/{project}-", "/aws/bedrock-agentcore/runtimes/{project}-")


class BotoAccountReader:
    def __init__(self, session, project: str = PROJECT) -> None:
        self.project = project
        self.cloudformation = session.client("cloudformation")
        self.s3 = session.client("s3")
        self.secretsmanager = session.client("secretsmanager")
        self.logs = session.client("logs")

    def stacks(self) -> list[tuple[str, dict[str, str]]]:
        found = []
        pages = self.cloudformation.get_paginator("list_stacks").paginate(
            StackStatusFilter=list(LIVE_STACKS)
        )
        for page in pages:
            for summary in page["StackSummaries"]:
                name = summary["StackName"]
                if name.startswith(f"{self.project}-"):
                    found.append((name, self._stack_tags(name)))
        return found

    def retained_resources(self, stack: str) -> list[tuple[str, str]]:
        template = self.cloudformation.get_template(StackName=stack)["TemplateBody"]
        if isinstance(template, str):
            template = json.loads(template)
        retained = {
            logical_id
            for logical_id, resource in (template.get("Resources") or {}).items()
            if resource.get("DeletionPolicy") == RETAIN
        }
        found = []
        pages = self.cloudformation.get_paginator("list_stack_resources").paginate(StackName=stack)
        for page in pages:
            for summary in page["StackResourceSummaries"]:
                if summary["LogicalResourceId"] in retained:
                    found.append((summary["ResourceType"], summary.get("PhysicalResourceId", "")))
        return found

    def buckets(self) -> list[tuple[str, dict[str, str]]]:
        names = [
            bucket["Name"]
            for bucket in self.s3.list_buckets()["Buckets"]
            if bucket["Name"].startswith(f"{self.project}-")
        ]
        return [(name, self._bucket_tags(name)) for name in names]

    def secrets(self) -> list[tuple[str, dict[str, str]]]:
        found = []
        pages = self.secretsmanager.get_paginator("list_secrets").paginate(
            IncludePlannedDeletion=True,
            Filters=[{"Key": "name", "Values": [f"{self.project}/"]}],
        )
        for page in pages:
            for secret in page["SecretList"]:
                tags = {tag["Key"]: tag["Value"] for tag in secret.get("Tags") or []}
                found.append((secret["Name"], tags))
        return found

    def log_groups(self) -> list[tuple[str, dict[str, str]]]:
        found = []
        for template in LOG_PREFIXES:
            prefix = template.format(project=self.project)
            pages = self.logs.get_paginator("describe_log_groups").paginate(
                logGroupNamePrefix=prefix
            )
            for page in pages:
                for group in page["logGroups"]:
                    name = group["logGroupName"]
                    found.append((name, self._log_group_tags(group["arn"])))
        return found

    def _stack_tags(self, stack: str) -> dict[str, str]:
        described = self.cloudformation.describe_stacks(StackName=stack)["Stacks"][0]
        return {tag["Key"]: tag["Value"] for tag in described.get("Tags") or []}

    def _bucket_tags(self, bucket: str) -> dict[str, str]:
        try:
            tagging = self.s3.get_bucket_tagging(Bucket=bucket)
        except self.s3.exceptions.ClientError:
            return {}
        return {tag["Key"]: tag["Value"] for tag in tagging.get("TagSet") or []}

    def _log_group_tags(self, arn: str) -> dict[str, str]:
        return self.logs.list_tags_for_resource(resourceArn=arn.rstrip(":*")).get("tags") or {}
