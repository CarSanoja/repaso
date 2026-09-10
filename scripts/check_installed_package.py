"""Run from outside a checkout to verify the installed distribution and both journeys."""

import asyncio
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.config.settings import Settings
from repaso.simulator.demo_scenario import run_demo_scenario, scenario_settings


async def check():
    for package, names in {
        "repaso.api": ["static/judge.html", "static/judge.css", "static/judge.js"],
        "repaso.simulator": [
            "cassettes/demo_fracciones.jsonl",
            "cassettes/demo_fracciones.provenance.json",
        ],
        "repaso.tools": ["fixtures/curriculum_math_primary.json"],
    }.items():
        for name in names:
            assert files(package).joinpath(name).is_file(), (package, name)
    with TemporaryDirectory(prefix="repaso-installed-") as root:
        settings = Settings(local_mode=True, local_data_dir=Path(root) / "api")
        app = create_app(build_container(settings, judge_code="PACKAGE-CHECK"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in [
                "/health",
                "/healthz",
                "/readyz",
                "/judge/",
                "/judge/assets/judge.css",
                "/judge/assets/judge.js",
            ]:
                response = await client.get(path)
                assert response.status_code == 200, (path, response.text)
            assert (
                await client.post("/judge/login", json={"code": "PACKAGE-CHECK"})
            ).status_code == 200
        for decision in ["teacher_note", "reduce_load"]:
            result = await run_demo_scenario(
                scenario_settings(Path(root) / decision), decision=decision
            )
            assert not result.failures, result.failures
            assert len(result.checkpoints) == 7
            print(f"{decision}: {len(result.beats)} checks, seven stages, passed")
    print("Installed package, HTTP routes, assets and complete journeys verified")


if __name__ == "__main__":
    asyncio.run(check())
