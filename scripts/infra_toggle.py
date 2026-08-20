import argparse
import sys

import boto3

SCHEDULE_GROUP = "repaso"
EVENT_BUS = "repaso"


def toggle_schedules(client, enable: bool) -> int:
    count = 0
    paginator = client.get_paginator("list_schedules")
    for page in paginator.paginate(GroupName=SCHEDULE_GROUP):
        for item in page["Schedules"]:
            schedule = client.get_schedule(GroupName=SCHEDULE_GROUP, Name=item["Name"])
            client.update_schedule(
                GroupName=SCHEDULE_GROUP,
                Name=schedule["Name"],
                ScheduleExpression=schedule["ScheduleExpression"],
                FlexibleTimeWindow=schedule["FlexibleTimeWindow"],
                Target=schedule["Target"],
                State="ENABLED" if enable else "DISABLED",
            )
            count += 1
    return count


def toggle_rules(client, enable: bool) -> int:
    count = 0
    paginator = client.get_paginator("list_rules")
    for page in paginator.paginate(EventBusName=EVENT_BUS):
        for rule in page["Rules"]:
            if enable:
                client.enable_rule(Name=rule["Name"], EventBusName=EVENT_BUS)
            else:
                client.disable_rule(Name=rule["Name"], EventBusName=EVENT_BUS)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(prog="infra_toggle")
    parser.add_argument("state", choices=["on", "off"])
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    enable = args.state == "on"

    session = boto3.Session(region_name=args.region)
    schedules = toggle_schedules(session.client("scheduler"), enable)
    rules = toggle_rules(session.client("events"), enable)
    print(f"{'enabled' if enable else 'disabled'}: {schedules} schedules, {rules} rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
