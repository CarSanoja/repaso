from pathlib import Path

from strands.models.model import Model

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.context import Services
from repaso.simulator.demo_scenario import START
from repaso.simulator.offline_services import assemble_services
from repaso.tools.llm import build_model
from repaso.tools.retrying_model import RetryingModel

WHAT_THIS_IS = (
    "One recording of the demonstration journey against Amazon Bedrock on-demand "
    "inference: one entry per call, in the order the journey made them, each routed to "
    "the model its role is bound to in src/repaso/config/models.py. Token counts are the "
    "ones the provider reported and dollars are priced from the dated table in "
    "src/repaso/config/pricing.py."
)
WHAT_THIS_IS_NOT = (
    "Not a live run. Replaying this cassette calls nothing and spends nothing, and a "
    "replay is not evidence that the models would answer this way again. One recording "
    "is not a rate, and nothing here measures tutoring quality or a family outcome."
)


def live_model_settings(settings: Settings, region: str, destination: Path) -> Settings:
    return settings.model_copy(
        update={
            "local_mode": False,
            "aws_region": region,
            "cassette_path": None,
            "record_cassette_path": destination,
        }
    )


def recording_models(
    settings: Settings, region: str, destination: Path
) -> dict[ModelRole, Model]:
    live = live_model_settings(settings, region, destination)
    return {role: RetryingModel(build_model(role, live)) for role in ModelRole}


def build_recording_services(settings: Settings, region: str, destination: Path) -> Services:
    return assemble_services(
        settings, SimClock(START), recording_models(settings, region, destination)
    )
