from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFilter

from repaso.core.harness.legibility import (
    DEFAULT_MIN_CONFIDENCE,
    MAX_SCORE,
    effective_confidence,
    legibility_score,
    needs_rephoto,
)

BLUR_RADIUS = 6


def make_sharp_image(width: int = 320, height: int = 240) -> Image.Image:
    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)
    for y in range(height // 12, height, height // 10):
        draw.line((12, y, width - 12, y), fill=0, width=2)
    for x in range(width // 16, width, width // 9):
        draw.rectangle((x, height // 8, x + width // 32, height - height // 8), fill=0)
    draw.text((16, 6), "REPASO 2026", fill=0)
    return image


def encode(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def sharp_bytes() -> bytes:
    return encode(make_sharp_image())


def blurred_bytes() -> bytes:
    return encode(make_sharp_image().filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS)))


def flat_bytes() -> bytes:
    return encode(Image.new("L", (320, 240), color=128))


def test_sharp_page_scores_above_blurred_and_blurred_above_flat():
    sharp = legibility_score(sharp_bytes())
    blurred = legibility_score(blurred_bytes())
    flat = legibility_score(flat_bytes())
    assert sharp > blurred > flat


def test_flat_page_carries_no_legibility_signal():
    assert legibility_score(flat_bytes()) == 0.0


def test_score_is_deterministic_for_identical_bytes():
    data = sharp_bytes()
    assert legibility_score(data) == legibility_score(data)
    assert legibility_score(data) == legibility_score(sharp_bytes())


def test_score_stays_within_cap_for_oversized_photo():
    oversized = encode(make_sharp_image(width=2400, height=1800))
    score = legibility_score(oversized)
    assert 0.0 < score <= MAX_SCORE


def test_empty_payload_is_rejected():
    with pytest.raises(ValueError):
        legibility_score(b"")


def test_confidence_passes_through_at_and_above_floor():
    assert effective_confidence(0.9, score=200.0, blur_floor=100.0) == 0.9
    assert effective_confidence(0.9, score=100.0, blur_floor=100.0) == 0.9


def test_confidence_is_discounted_proportionally_below_floor():
    assert effective_confidence(0.8, score=50.0, blur_floor=100.0) == pytest.approx(0.4)
    assert effective_confidence(0.8, score=0.0, blur_floor=100.0) == 0.0


def test_confidence_is_clamped_to_unit_range():
    assert effective_confidence(1.4, score=200.0, blur_floor=100.0) == 1.0
    assert effective_confidence(-0.2, score=50.0, blur_floor=100.0) == 0.0


def test_effective_confidence_rejects_non_positive_floor():
    with pytest.raises(ValueError):
        effective_confidence(0.9, score=50.0, blur_floor=0.0)


def test_blurred_page_is_flagged_for_rephoto():
    floor = legibility_score(sharp_bytes()) / 2
    blurred = legibility_score(blurred_bytes())
    assert needs_rephoto(
        0.9, score=blurred, blur_floor=floor, min_confidence=DEFAULT_MIN_CONFIDENCE
    )


def test_sharp_page_is_accepted_without_rephoto():
    floor = legibility_score(sharp_bytes()) / 2
    sharp = legibility_score(sharp_bytes())
    assert not needs_rephoto(0.9, score=sharp, blur_floor=floor)


def test_rephoto_boundary_sits_at_min_confidence():
    assert not needs_rephoto(1.0, score=60.0, blur_floor=100.0, min_confidence=0.6)
    assert needs_rephoto(1.0, score=59.0, blur_floor=100.0, min_confidence=0.6)
