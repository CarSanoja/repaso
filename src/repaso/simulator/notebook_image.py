from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from repaso.tools.image_text import TEXT_CHUNK_KEY

PAGE_WIDTH = 720
MARGIN = 28
LINE_HEIGHT = 30
FONT_SIZE = 19
PAPER = (252, 251, 246)
RULE = (186, 206, 228)
INK = (22, 24, 30)


def render_notebook_png(text: str) -> bytes:
    lines = text.splitlines() or [""]
    height = MARGIN * 2 + LINE_HEIGHT * len(lines)
    page = Image.new("RGB", (PAGE_WIDTH, height), PAPER)
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=FONT_SIZE)
    for index in range(len(lines)):
        baseline = MARGIN + index * LINE_HEIGHT + LINE_HEIGHT - 5
        draw.line([(MARGIN, baseline), (PAGE_WIDTH - MARGIN, baseline)], fill=RULE)
    for index, line in enumerate(lines):
        draw.text((MARGIN, MARGIN + index * LINE_HEIGHT), line, fill=INK, font=font)
    carried = PngInfo()
    carried.add_text(TEXT_CHUNK_KEY, text)
    buffer = BytesIO()
    page.save(buffer, format="PNG", pnginfo=carried)
    return buffer.getvalue()
