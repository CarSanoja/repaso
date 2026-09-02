from io import BytesIO

from PIL import Image

from repaso.core.harness.legibility import DEFAULT_MIN_CONFIDENCE, legibility_score, needs_rephoto
from repaso.schemas.channel import MediaKind
from repaso.simulator.notebook_image import PAGE_WIDTH, render_notebook_png
from repaso.tools.media_fetcher import PNG, sniff_content_type
from repaso.tools.ocr import LocalTextExtractor

BLUR_FLOOR = 300.0
NOTEBOOK = (
    "Matemática — 4to grado\n"
    "Tema: fracciones equivalentes\n"
    "1) 1/2 = 2/4\n"
    "2) Completa: 2/5 = ?/10\n"
    "3) ¿Es 2/6 equivalente a 1/3? Explica."
)


def test_the_page_is_a_png_a_reader_can_open():
    data = render_notebook_png(NOTEBOOK)
    with Image.open(BytesIO(data)) as page:
        assert page.format == "PNG"
        assert page.width == PAGE_WIDTH
    assert sniff_content_type(data) == PNG


def test_the_page_grows_with_the_lines_it_renders():
    short = render_notebook_png("una línea")
    long = render_notebook_png(NOTEBOOK)
    with Image.open(BytesIO(short)) as first, Image.open(BytesIO(long)) as second:
        assert second.height > first.height


def test_rendered_text_clears_the_blur_floor():
    data = render_notebook_png(NOTEBOOK)
    score = legibility_score(data)
    assert score > BLUR_FLOOR
    assert not needs_rephoto(0.99, score, BLUR_FLOOR, DEFAULT_MIN_CONFIDENCE)


def test_the_local_extractor_reads_the_page_it_was_given():
    result = LocalTextExtractor().extract(render_notebook_png(NOTEBOOK), MediaKind.PHOTO)
    assert result.text == NOTEBOOK
    assert result.confidence > DEFAULT_MIN_CONFIDENCE


def test_the_same_page_renders_byte_for_byte_the_same():
    assert render_notebook_png(NOTEBOOK) == render_notebook_png(NOTEBOOK)
