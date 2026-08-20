from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

MAX_DIMENSION = 1024
LAPLACIAN_KERNEL = (0, -1, 0, -1, 4, -1, 0, -1, 0)
LAPLACIAN_SCALE = 1
LAPLACIAN_OFFSET = 128
CONTRAST_REFERENCE = 64.0
MAX_SCORE = 10000.0
DEFAULT_MIN_CONFIDENCE = 0.6


def _clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _downscale(image: Image.Image) -> Image.Image:
    longest = max(image.size)
    if longest <= MAX_DIMENSION:
        return image
    ratio = MAX_DIMENSION / longest
    width = max(1, round(image.width * ratio))
    height = max(1, round(image.height * ratio))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _grayscale(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as opened:
        gray = opened.convert("L")
    return _downscale(gray)


def _blur_variance(gray: Image.Image) -> float:
    kernel = ImageFilter.Kernel(
        (3, 3), LAPLACIAN_KERNEL, scale=LAPLACIAN_SCALE, offset=LAPLACIAN_OFFSET
    )
    return ImageStat.Stat(gray.filter(kernel)).var[0]


def _contrast_std(gray: Image.Image) -> float:
    return ImageStat.Stat(gray).stddev[0]


def legibility_score(image_bytes: bytes) -> float:
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")
    gray = _grayscale(image_bytes)
    raw = _blur_variance(gray) * (_contrast_std(gray) / CONTRAST_REFERENCE)
    return min(MAX_SCORE, max(0.0, raw))


def effective_confidence(ocr_confidence: float, score: float, blur_floor: float) -> float:
    if blur_floor <= 0:
        raise ValueError("blur_floor must be positive")
    confidence = _clamp_unit(ocr_confidence)
    if score >= blur_floor:
        return confidence
    return _clamp_unit(confidence * max(0.0, score) / blur_floor)


def needs_rephoto(
    ocr_confidence: float,
    score: float,
    blur_floor: float,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> bool:
    return effective_confidence(ocr_confidence, score, blur_floor) < min_confidence
