from io import BytesIO

from PIL import Image, UnidentifiedImageError

TEXT_CHUNK_KEY = "repaso:text"


def embedded_text(data: bytes) -> str | None:
    if not data:
        return None
    try:
        with Image.open(BytesIO(data)) as opened:
            value = opened.info.get(TEXT_CHUNK_KEY)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
