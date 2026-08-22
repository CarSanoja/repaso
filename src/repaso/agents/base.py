from pydantic import BaseModel

from repaso.tools.llm import PlaybackExhausted


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


class StructuredCallFailed(RuntimeError):
    pass


async def structured[T: BaseModel](model, output_model: type[T], system: str, text: str) -> T:
    events = model.structured_output(output_model, [user_message(text)], system_prompt=system)
    output: T | None = None
    try:
        async for event in events:
            if "output" in event:
                output = event["output"]
    except PlaybackExhausted:
        raise
    except Exception as error:
        raise StructuredCallFailed(str(error)) from error
    if output is None:
        raise StructuredCallFailed(f"model returned no output for {output_model.__name__}")
    return output
