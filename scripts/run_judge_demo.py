"""Run the isolated judge UI. No AWS account or Telegram token is needed."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.config.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--code", default="REPASO-DEMO")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="repaso-judge-ui-") as root:
        container = build_container(
            Settings(local_mode=True, local_data_dir=Path(root)), judge_code=args.code
        )
        print(f"Judge experience: http://127.0.0.1:{args.port}/judge/ · code: {args.code}")
        uvicorn.run(create_app(container), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
