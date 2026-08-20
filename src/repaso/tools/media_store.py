import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from repaso.config.settings import Settings

MEDIA_DIRNAME = "media"
CONTENT_TYPE_INDEX = "media_content_types.json"
MISSING_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


@runtime_checkable
class MediaStore(Protocol):
    def put(self, ref: str, data: bytes, content_type: str) -> None: ...

    def get(self, ref: str) -> bytes | None: ...

    def exists(self, ref: str) -> bool: ...


def normalize_ref(ref: str) -> str:
    cleaned = ref.strip().strip("/")
    if not cleaned:
        raise ValueError("media ref must not be empty")
    parts = cleaned.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"media ref must not traverse paths: {ref}")
    if "\\" in cleaned or ":" in cleaned:
        raise ValueError(f"media ref must not contain path separators: {ref}")
    return "/".join(parts)


class LocalMediaStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._media_dir = self._root / MEDIA_DIRNAME
        self._index_path = self._root / CONTENT_TYPE_INDEX

    @property
    def media_dir(self) -> Path:
        return self._media_dir

    def put(self, ref: str, data: bytes, content_type: str) -> None:
        key = normalize_ref(ref)
        path = self._media_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._record_content_type(key, content_type)

    def get(self, ref: str) -> bytes | None:
        path = self._media_dir / normalize_ref(ref)
        if not path.is_file():
            return None
        return path.read_bytes()

    def exists(self, ref: str) -> bool:
        return (self._media_dir / normalize_ref(ref)).is_file()

    def content_type(self, ref: str) -> str | None:
        return self._read_index().get(normalize_ref(ref))

    def _read_index(self) -> dict[str, str]:
        if not self._index_path.is_file():
            return {}
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _record_content_type(self, key: str, content_type: str) -> None:
        index = self._read_index()
        index[key] = content_type
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")


class S3MediaStore:
    def __init__(self, bucket: str) -> None:
        if not bucket:
            raise ValueError("bucket must not be empty")
        self._bucket = bucket

    def put(self, ref: str, data: bytes, content_type: str) -> None:
        self._client().put_object(
            Bucket=self._bucket,
            Key=normalize_ref(ref),
            Body=data,
            ContentType=content_type,
        )

    def get(self, ref: str) -> bytes | None:
        client = self._client()
        try:
            response = client.get_object(Bucket=self._bucket, Key=normalize_ref(ref))
        except client.exceptions.ClientError as error:
            if _is_missing(error):
                return None
            raise
        return response["Body"].read()

    def exists(self, ref: str) -> bool:
        client = self._client()
        try:
            client.head_object(Bucket=self._bucket, Key=normalize_ref(ref))
        except client.exceptions.ClientError as error:
            if _is_missing(error):
                return False
            raise
        return True

    def _client(self) -> Any:
        from repaso.config.clients import s3_client

        client = s3_client()
        if client is None:
            raise RuntimeError("s3 client is unavailable in local mode")
        return client


def _is_missing(error: Exception) -> bool:
    response = getattr(error, "response", {}) or {}
    code = str(response.get("Error", {}).get("Code", ""))
    status = str(response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
    return code in MISSING_CODES or status == "404"


def build_media_store(settings: Settings) -> MediaStore:
    if settings.local_mode:
        return LocalMediaStore(settings.local_data_dir)
    return S3MediaStore(settings.media_bucket)
