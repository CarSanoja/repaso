from typing import Any, get_origin

from pydantic import BaseModel, model_validator

from repaso.tools.cassette_model import CassetteExhausted
from repaso.tools.llm import PlaybackExhausted
from repaso.tools.model_limits import ModelLimitReached


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


class ModelOutput(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def an_absent_list_is_an_empty_one(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        emptied = {
            name: []
            for name, field in cls.model_fields.items()
            if data.get(name, ...) is None and get_origin(field.annotation) is list
        }
        return {**data, **emptied} if emptied else data


class StructuredCallFailed(RuntimeError):
    pass


async def structured[T: BaseModel](model, output_model: type[T], system: str, text: str) -> T:
    events = model.structured_output(output_model, [user_message(text)], system_prompt=system)
    output: T | None = None
    try:
        async for event in events:
            if "output" in event:
                output = event["output"]
    except (CassetteExhausted, PlaybackExhausted, ModelLimitReached):
        raise
    except Exception as error:
        raise StructuredCallFailed(str(error)) from error
    if output is None:
        raise StructuredCallFailed(f"model returned no output for {output_model.__name__}")
    return output
