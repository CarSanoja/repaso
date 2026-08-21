import pytest

from repaso.config.settings import Settings
from repaso.schemas.channel import MediaKind
from repaso.tools.media_store import (
    MEDIA_DIRNAME,
    LocalMediaStore,
    MediaStore,
    build_media_store,
)
from repaso.tools.ocr import (
    DECODED_TEXT_CONFIDENCE,
    ExtractResult,
    LocalTextExtractor,
    TextExtractor,
    build_text_extractor,
)

PHOTO_REF = "families/fam-1/materials/mat-1.jpg"
PHOTO_BYTES = b"\x89PNG\r\n\x1a\n binary payload"
BINARY_BYTES = b"\xff\xfe\x00\x01\x89PNG\r\n"
TRAVERSAL_REFS = ["../escape.jpg", "families/../../escape.jpg", "..", "a/../../b.jpg"]


def make_store(settings: Settings) -> LocalMediaStore:
    return LocalMediaStore(settings.local_data_dir)


def test_a_stored_object_comes_back_byte_for_byte(settings):
    store = make_store(settings)
    store.put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    assert store.get(PHOTO_REF) == PHOTO_BYTES


def test_exists_flips_from_false_to_true_after_put(settings):
    store = make_store(settings)
    assert store.exists(PHOTO_REF) is False
    store.put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    assert store.exists(PHOTO_REF) is True


def test_put_creates_the_nested_directories_under_the_data_dir(settings):
    assert not settings.local_data_dir.exists()
    store = make_store(settings)
    store.put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    assert (settings.local_data_dir / MEDIA_DIRNAME / PHOTO_REF).is_file()


def test_a_later_put_overwrites_the_same_ref(settings):
    store = make_store(settings)
    store.put(PHOTO_REF, b"first", "image/jpeg")
    store.put(PHOTO_REF, b"second", "image/jpeg")
    assert store.get(PHOTO_REF) == b"second"


def test_a_missing_ref_reads_as_none_and_does_not_exist(settings):
    store = make_store(settings)
    assert store.get("families/fam-1/never-uploaded.jpg") is None
    assert store.exists("families/fam-1/never-uploaded.jpg") is False


def test_the_content_type_given_at_put_is_kept_with_the_object(settings):
    store = make_store(settings)
    store.put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    store.put("families/fam-1/materials/mat-2.pdf", b"%PDF-1.7", "application/pdf")
    assert store.content_type(PHOTO_REF) == "image/jpeg"
    assert store.content_type("families/fam-1/materials/mat-2.pdf") == "application/pdf"


@pytest.mark.parametrize("ref", TRAVERSAL_REFS)
def test_a_traversing_ref_is_rejected_on_every_operation(settings, ref):
    store = make_store(settings)
    with pytest.raises(ValueError):
        store.put(ref, PHOTO_BYTES, "image/jpeg")
    with pytest.raises(ValueError):
        store.get(ref)
    with pytest.raises(ValueError):
        store.exists(ref)


def test_a_traversing_ref_never_writes_outside_the_media_dir(settings, tmp_path):
    store = make_store(settings)
    with pytest.raises(ValueError):
        store.put("../../escape.jpg", PHOTO_BYTES, "image/jpeg")
    assert not (tmp_path / "escape.jpg").exists()


@pytest.mark.parametrize("ref", ["", "   ", "/", "///"])
def test_an_empty_ref_is_rejected(settings, ref):
    with pytest.raises(ValueError):
        make_store(settings).put(ref, PHOTO_BYTES, "image/jpeg")


def test_leading_and_trailing_slashes_address_the_same_object(settings):
    store = make_store(settings)
    store.put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    assert store.get(f"/{PHOTO_REF}/") == PHOTO_BYTES


def test_utf8_payloads_extract_as_text_with_high_confidence():
    result = LocalTextExtractor().extract(b"Resolver 3x + 5 = 20\n", MediaKind.PHOTO)
    assert result == ExtractResult(text="Resolver 3x + 5 = 20", confidence=DECODED_TEXT_CONFIDENCE)


def test_accented_spanish_survives_the_round_trip():
    result = LocalTextExtractor().extract("¿Cuánto mide el ángulo?".encode(), MediaKind.PDF)
    assert result.text == "¿Cuánto mide el ángulo?"


def test_binary_garbage_extracts_as_empty_text_with_zero_confidence():
    result = LocalTextExtractor().extract(BINARY_BYTES, MediaKind.PHOTO)
    assert result == ExtractResult(text="", confidence=0.0)


def test_empty_and_blank_payloads_carry_no_confidence():
    extractor = LocalTextExtractor()
    assert extractor.extract(b"", MediaKind.PHOTO).confidence == 0.0
    assert extractor.extract(b"   \n\t ", MediaKind.PHOTO) == ExtractResult(text="", confidence=0.0)


def test_extract_result_confidence_stays_inside_the_unit_range():
    with pytest.raises(ValueError):
        ExtractResult(text="x", confidence=1.5)


def test_extract_result_is_frozen():
    with pytest.raises(ValueError):
        ExtractResult(text="x", confidence=0.5).text = "y"


def test_media_factory_returns_the_local_store_in_local_mode(settings):
    store = build_media_store(settings)
    assert isinstance(store, LocalMediaStore)
    assert store.media_dir == settings.local_data_dir / MEDIA_DIRNAME


def test_ocr_factory_returns_the_local_extractor_in_local_mode(settings):
    assert isinstance(build_text_extractor(settings), LocalTextExtractor)


def test_factory_store_writes_under_the_configured_data_dir(tmp_path):
    settings = Settings(local_mode=True, local_data_dir=tmp_path / "local_data")
    build_media_store(settings).put(PHOTO_REF, PHOTO_BYTES, "image/jpeg")
    assert (tmp_path / "local_data" / MEDIA_DIRNAME / PHOTO_REF).is_file()


def test_local_implementations_satisfy_their_protocols_without_inheriting_them(settings):
    assert isinstance(build_media_store(settings), MediaStore)
    assert isinstance(build_text_extractor(settings), TextExtractor)
    assert MediaStore not in LocalMediaStore.__mro__
    assert TextExtractor not in LocalTextExtractor.__mro__
