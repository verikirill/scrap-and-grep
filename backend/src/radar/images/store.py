"""Copies of pictures, for when a link is not enough.

Most pictures are used by their address: the browser and Telegram fetch them
themselves. A copy is kept when that fails (a site that refuses hotlinking)
and for the video renderer, which works in a network without internet. Copies
go to the media volume by default, or to S3 (MinIO or any compatible store)
when RADAR_IMAGE_STORE=s3.
"""

import asyncio
import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from radar.config import get_settings

KEY_RE = re.compile(r"^[0-9a-f]{40}\.(jpg|png|webp|gif)$")
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}


class ImageStore(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes | None: ...


def content_type(key: str) -> str:
    return CONTENT_TYPES[key.rsplit(".", 1)[1]]


class LocalImageStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        if not KEY_RE.match(key):
            raise ValueError("not an image key")
        return self._root / key[:2] / key

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(path.suffix + ".part")
            partial.write_bytes(data)
            partial.replace(path)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return await asyncio.to_thread(lambda: path.read_bytes() if path.is_file() else None)


class S3ImageStore:
    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        secure: bool,
        region: str | None,
    ) -> None:
        from minio import Minio

        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        self._bucket = bucket
        self._ready = False

    def _ensure_bucket(self) -> None:
        if not self._ready:
            if not self._client.bucket_exists(bucket_name=self._bucket):
                self._client.make_bucket(bucket_name=self._bucket)
            self._ready = True

    async def put(self, key: str, data: bytes) -> None:
        if not KEY_RE.match(key):
            raise ValueError("not an image key")

        def upload() -> None:
            self._ensure_bucket()
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=key,
                data=io.BytesIO(data),
                length=len(data),
                content_type=content_type(key),
            )

        await asyncio.to_thread(upload)

    async def get(self, key: str) -> bytes | None:
        if not KEY_RE.match(key):
            raise ValueError("not an image key")
        from minio.error import S3Error

        def download() -> bytes | None:
            self._ensure_bucket()
            try:
                response = self._client.get_object(bucket_name=self._bucket, object_name=key)
            except S3Error as exc:
                if exc.code in {"NoSuchKey", "NoSuchObject"}:
                    return None
                raise
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(download)


@lru_cache
def get_image_store() -> ImageStore:
    settings = get_settings()
    if settings.image_store == "s3":
        secret = settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else ""
        return S3ImageStore(
            endpoint=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=secret,
            secure=settings.s3_secure,
            region=settings.s3_region or None,
        )
    return LocalImageStore(Path(settings.media_dir) / "images")
