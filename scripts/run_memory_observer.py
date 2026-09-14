"""Run a loopback observer of AWS, or a separately isolated local rehearsal.

The AWS mode only reads. The API container uses local sender/publisher adapters
and has no webhook secret, so this process cannot send to Telegram or publish work.
"""

import argparse
import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.api.memory_events import CloudEventFeed
from repaso.config.clients import reset_client_cache
from repaso.config.settings import Settings, clear_settings_cache
from repaso.simulator.memory_rehearsal import FAMILY_ID, MemoryRehearsal
from repaso.tools.state_store import build_state_store


def make_app(args, root: Path):
    local = Settings(
        _env_file=None,
        local_mode=True,
        local_data_dir=root,
        judge_family_ids=FAMILY_ID if args.rehearsal else args.family_id,
    )
    container = build_container(local, judge_code=args.code)
    app = create_app(container)
    if args.rehearsal:
        rehearsal = MemoryRehearsal(local)
        asyncio.run(rehearsal.prepare())
        container.clock = rehearsal.clock
        app.state.memory_rehearsal = rehearsal
    else:
        if not args.family_id:
            raise ValueError("AWS observation requires an explicit --family-id allowlist")
        os.environ.update(
            AWS_PROFILE=args.profile,
            AWS_DEFAULT_REGION=args.region,
            REPASO_LOCAL_MODE="false",
            REPASO_AWS_REGION=args.region,
        )
        clear_settings_cache()
        reset_client_cache()
        container.settings = local.model_copy(
            update={"local_mode": False, "aws_region": args.region, "ddb_table": args.table}
        )
        container.store = build_state_store(container.settings)
        app.state.memory_events = CloudEventFeed(
            args.region,
            container.settings.agentcore_runtime_arn_parameter,
            history_minutes=args.history_minutes,
        )
    return app


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rehearsal", action="store_true")
    p.add_argument("--family-id", default="", help="Comma-separated explicit family allowlist")
    p.add_argument("--profile", default="quanta")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--table", default="repaso")
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--code", default="REPASO-VIEW")
    p.add_argument(
        "--history-minutes",
        type=int,
        default=1440,
        help="Initial CloudWatch lookback for episode reconstruction (default: 24 hours)",
    )
    args = p.parse_args()
    if not 1 <= args.history_minutes <= 10080:
        p.error("--history-minutes must be between 1 and 10080")
    with TemporaryDirectory(prefix="repaso-memory-") as root:
        app = make_app(args, Path(root))
        print(f"Memory observer: http://127.0.0.1:{args.port}/judge/memory/", flush=True)
        print("Mode: " + ("LOCAL REHEARSAL" if args.rehearsal else "AWS READ-ONLY"), flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
