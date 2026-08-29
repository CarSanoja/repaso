from typing import Any

from repaso.runtime.entrypoint import invoke_async

RUNTIME_APP_ATTR = "app"


async def agentcore_entrypoint(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return await invoke_async(payload)


def build_runtime_app() -> Any:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    runtime = BedrockAgentCoreApp()
    runtime.entrypoint(agentcore_entrypoint)
    return runtime


def __getattr__(name: str) -> Any:
    if name == RUNTIME_APP_ATTR:
        return build_runtime_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    build_runtime_app().run()


if __name__ == "__main__":
    main()
