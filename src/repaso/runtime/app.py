from typing import Any

from repaso.runtime.entrypoint import invoke_async


async def agentcore_entrypoint(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return await invoke_async(payload)


def build_runtime_app() -> Any:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()
    app.entrypoint(agentcore_entrypoint)
    return app


def main() -> None:
    build_runtime_app().run()
