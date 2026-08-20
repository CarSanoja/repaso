from datetime import datetime

from repaso.schemas.common import FrozenStrictModel


class ConsentRecord(FrozenStrictModel):
    version: str
    accepted_at: datetime
    chat_ref: str
