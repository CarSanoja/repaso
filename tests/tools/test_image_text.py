from io import BytesIO

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from repaso.tools.image_text import TEXT_CHUNK_KEY, embedded_text

NOTE = "Tema: fracciones equivalentes\n1) 1/2 = 2/4"


def png_bytes(carried: str | None) -> bytes:
    image = Image.new("RGB", (8, 8), (255, 255, 255))
    info = PngInfo()
    if carried is not None:
        info.add_text(TEXT_CHUNK_KEY, carried)
    buffer = BytesIO()
    image.save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


def test_a_png_gives_back_the_text_it_carries():
    assert embedded_text(png_bytes(NOTE)) == NOTE


def test_a_png_carrying_nothing_reads_as_no_text():
    assert embedded_text(png_bytes(None)) is None


def test_a_blank_chunk_reads_as_no_text():
    assert embedded_text(png_bytes("   \n  ")) is None


def test_surrounding_whitespace_is_trimmed():
    assert embedded_text(png_bytes(f"\n  {NOTE}  \n")) == NOTE


def test_bytes_that_are_not_an_image_read_as_no_text():
    assert embedded_text(b"\x89PNG\r\n\x1a\n truncated before the header") is None


def test_empty_bytes_read_as_no_text():
    assert embedded_text(b"") is None


def test_a_jpeg_without_the_chunk_reads_as_no_text():
    image = Image.new("RGB", (8, 8), (200, 200, 200))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    assert embedded_text(buffer.getvalue()) is None
