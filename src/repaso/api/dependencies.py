from dataclasses import dataclass

from repaso.config.settings import Settings
from repaso.tools.event_bus import EventPublisher, build_event_publisher
from repaso.tools.media_fetcher import MediaFetcher, build_media_fetcher
from repaso.tools.state_store import StateStore, build_state_store
from repaso.tools.telegram import ChannelSender, build_channel_sender


@dataclass
class AppContainer:
    settings: Settings
    store: StateStore
    sender: ChannelSender
    fetcher: MediaFetcher
    publisher: EventPublisher
    telegram_secret: str = ""
    judge_code: str = ""


def build_container(
    settings: Settings,
    telegram_secret: str = "",
    judge_code: str = "",
    telegram_token: str | None = None,
) -> AppContainer:
    return AppContainer(
        settings=settings,
        store=build_state_store(settings),
        sender=build_channel_sender(settings, telegram_token),
        fetcher=build_media_fetcher(settings, telegram_token),
        publisher=build_event_publisher(settings),
        telegram_secret=telegram_secret,
        judge_code=judge_code,
    )
