from teardown_plan import PROJECT, Target, refusal

BATCH = 1000
GONE = "already gone"
RESERVED = "inside a recovery window already opened: the name stays reserved until it closes"
STACK_WAITER = "stack_delete_complete"
WAIT_DELAY = 15
WAIT_ATTEMPTS = 120


class OutsideNamespace(Exception):
    pass


class BotoRemover:
    def __init__(self, session, project: str = PROJECT) -> None:
        self.project = project
        self.cloudformation = session.client("cloudformation")
        self.s3 = session.client("s3")
        self.secretsmanager = session.client("secretsmanager")
        self.logs = session.client("logs")

    def empty(self, target: Target) -> str:
        self.verify(target)
        removed = 0
        pages = self.s3.get_paginator("list_object_versions").paginate(Bucket=target.name)
        for page in pages:
            doomed = [
                {"Key": entry["Key"], "VersionId": entry["VersionId"]}
                for key in ("Versions", "DeleteMarkers")
                for entry in page.get(key) or []
            ]
            for start in range(0, len(doomed), BATCH):
                self.s3.delete_objects(
                    Bucket=target.name, Delete={"Objects": doomed[start : start + BATCH]}
                )
            removed += len(doomed)
        return f"emptied {removed} object version(s)"

    def remove(self, target: Target) -> str:
        self.verify(target)
        handlers = {
            "stack": self._stack,
            "bucket": self._bucket,
            "secret": self._secret,
            "log group": self._log_group,
        }
        handler = handlers.get(target.kind)
        if handler is None:
            raise OutsideNamespace(f"no removal is defined for {target}")
        return handler(target.name)

    def verify(self, target: Target) -> None:
        problem = refusal(target, self.project)
        if problem:
            raise OutsideNamespace(problem)

    def _stack(self, name: str) -> str:
        self.cloudformation.delete_stack(StackName=name)
        waiter = self.cloudformation.get_waiter(STACK_WAITER)
        waiter.wait(
            StackName=name,
            WaiterConfig={"Delay": WAIT_DELAY, "MaxAttempts": WAIT_ATTEMPTS},
        )
        return "deleted"

    def _bucket(self, name: str) -> str:
        try:
            self.s3.delete_bucket(Bucket=name)
        except self.s3.exceptions.NoSuchBucket:
            return GONE
        return "deleted"

    def _secret(self, name: str) -> str:
        try:
            self.secretsmanager.delete_secret(SecretId=name, ForceDeleteWithoutRecovery=True)
        except self.secretsmanager.exceptions.ResourceNotFoundException:
            return GONE
        except self.secretsmanager.exceptions.InvalidRequestException:
            return RESERVED
        return "deleted without a recovery window"

    def _log_group(self, name: str) -> str:
        try:
            self.logs.delete_log_group(logGroupName=name)
        except self.logs.exceptions.ResourceNotFoundException:
            return GONE
        return "deleted"
