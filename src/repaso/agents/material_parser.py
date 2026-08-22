from repaso.core.harness import effective_confidence, legibility_score, needs_rephoto
from repaso.schemas.channel import MediaKind
from repaso.schemas.material import Material, MaterialStatus
from repaso.tools.ocr import ExtractResult, TextExtractor

UNREADABLE_IMAGE = "unreadable_image"
BLURRY_PHOTO = "blurry_photo"
LOW_CONFIDENCE = "low_confidence"
EMPTY_TEXT = "empty_text"


def _illegible(material: Material, reason: str, **fields: float | None) -> Material:
    update: dict[str, object] = {
        "status": MaterialStatus.ILLEGIBLE,
        "rejection_reason": reason,
        "parsed_text": None,
    }
    update.update(fields)
    return material.model_copy(update=update)


def _parsed(
    material: Material, result: ExtractResult, score: float | None, effective: float
) -> Material:
    return material.model_copy(
        update={
            "status": MaterialStatus.PARSED,
            "parsed_text": result.text,
            "ocr_confidence": result.confidence,
            "legibility_score": score,
            "effective_confidence": effective,
            "rejection_reason": None,
        }
    )


def _parse_photo(
    material: Material,
    data: bytes,
    extractor: TextExtractor,
    blur_floor: float,
    min_confidence: float,
) -> Material:
    try:
        score = legibility_score(data)
    except (ValueError, OSError):
        return _illegible(material, UNREADABLE_IMAGE)
    result = extractor.extract(data, material.kind)
    effective = effective_confidence(result.confidence, score, blur_floor)
    if needs_rephoto(result.confidence, score, blur_floor, min_confidence):
        return _illegible(
            material,
            BLURRY_PHOTO,
            ocr_confidence=result.confidence,
            legibility_score=score,
            effective_confidence=effective,
        )
    return _parsed(material, result, score, effective)


def _parse_document(
    material: Material, data: bytes, extractor: TextExtractor, min_confidence: float
) -> Material:
    result = extractor.extract(data, material.kind)
    if not result.text.strip():
        return _illegible(material, EMPTY_TEXT, ocr_confidence=result.confidence)
    if result.confidence < min_confidence:
        return _illegible(
            material,
            LOW_CONFIDENCE,
            ocr_confidence=result.confidence,
            effective_confidence=result.confidence,
        )
    return _parsed(material, result, None, result.confidence)


def parse_material(
    material: Material,
    data: bytes,
    extractor: TextExtractor,
    blur_floor: float,
    min_confidence: float,
) -> Material:
    if material.kind is MediaKind.PHOTO:
        return _parse_photo(material, data, extractor, blur_floor, min_confidence)
    return _parse_document(material, data, extractor, min_confidence)
