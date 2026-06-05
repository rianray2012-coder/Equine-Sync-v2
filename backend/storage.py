"""
Object storage — provider-agnostic abstraction.

Phase-D scaffolding (Feb 19 2026). Designed against Cloudflare R2 as the
target production provider (S3-compatible), but the interface is provider-
neutral so we can swap to AWS S3 / Emergent storage / local disk without
touching callers.

Activation:
    Set the following env vars to switch from the default LocalDevStorage
    to R2/S3 in production:
        STORAGE_PROVIDER=r2 (or "s3")
        STORAGE_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
        STORAGE_REGION=auto
        STORAGE_ACCESS_KEY_ID=...
        STORAGE_SECRET_ACCESS_KEY=...
        STORAGE_BUCKET=equinesync-media
        STORAGE_PUBLIC_BASE_URL=https://media.equinesync.com   # CDN / public domain
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

logger = logging.getLogger(__name__)

# ---------- Domain types -----------------------------------------------------

MediaKind = Literal[
    "horse_photo",
    "completion_photo",
    "injury_photo",
    "document",
    "owner_upload",
]

ALLOWED_MIME = {
    "horse_photo":     {"image/jpeg", "image/png", "image/webp", "image/heic"},
    "completion_photo":{"image/jpeg", "image/png", "image/webp", "image/heic"},
    "injury_photo":    {"image/jpeg", "image/png", "image/webp", "image/heic"},
    "document":        {"application/pdf", "image/jpeg", "image/png"},
    "owner_upload":    {"image/jpeg", "image/png", "image/webp", "application/pdf"},
}

MAX_BYTES = {
    "horse_photo":     8 * 1024 * 1024,
    "completion_photo":8 * 1024 * 1024,
    "injury_photo":    8 * 1024 * 1024,
    "document":        20 * 1024 * 1024,
    "owner_upload":    10 * 1024 * 1024,
}


@dataclass(frozen=True)
class UploadIntent:
    """Returned by `prepare_upload` — the client uploads to upload_url, then POSTs
    the returned media_id back to the API to confirm.
    """
    media_id: str
    upload_url: str          # presigned PUT URL (empty for local stub)
    upload_method: str       # "PUT" | "POST" | "STUB"
    public_url: str          # where the asset will be readable once committed
    storage_key: str         # opaque key inside the bucket
    expires_at: str          # ISO


@dataclass(frozen=True)
class MediaRecord:
    """Persisted shape stored in `media` collection (Mongo)."""
    id: str
    tenant_id: str
    barn_id: str
    kind: str
    storage_key: str
    public_url: str
    mime_type: str
    byte_size: int
    uploaded_by_user_id: Optional[str]
    linked_horse_ids: list
    linked_task_id: Optional[str]
    linked_injury_id: Optional[str]
    created_at: str
    committed: bool


# ---------- Provider interface ----------------------------------------------

class StorageProvider:
    """Implement this for each backing store."""

    def name(self) -> str:
        raise NotImplementedError

    def prepare_upload(self, *, key: str, mime: str, byte_size: int, ttl_minutes: int = 15) -> UploadIntent:
        raise NotImplementedError

    def public_url_for(self, key: str) -> str:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError


# ---------- LocalDev (no-op) provider — used when no env credentials set ----

class LocalDevStorage(StorageProvider):
    """Returns stub presigned URLs that won't accept uploads. Lets the UI
    render the upload affordance during local dev without crashing.
    """

    def name(self) -> str:
        return "local_dev_stub"

    def prepare_upload(self, *, key: str, mime: str, byte_size: int, ttl_minutes: int = 15) -> UploadIntent:
        media_id = secrets.token_urlsafe(12)
        return UploadIntent(
            media_id=media_id,
            upload_url=f"/api/uploads/_stub_/{media_id}",
            upload_method="STUB",
            public_url=f"/api/uploads/_stub_/{media_id}/public",
            storage_key=key,
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat(),
        )

    def public_url_for(self, key: str) -> str:
        return f"/api/uploads/_stub_/{key}/public"

    async def delete(self, key: str) -> None:
        logger.info("LocalDevStorage: pretending to delete %s", key)


# ---------- R2 / S3-compatible provider (lazily imports boto3) --------------

class S3CompatibleStorage(StorageProvider):
    """Works for Cloudflare R2, AWS S3, MinIO, Backblaze B2, etc."""

    def __init__(self, *, endpoint_url: str, region: str, access_key: str,
                 secret_key: str, bucket: str, public_base_url: str):
        self.endpoint_url = endpoint_url
        self.region = region
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        try:
            import boto3  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "boto3 is required for S3-compatible storage. "
                "Add `boto3` to requirements.txt and reinstall."
            ) from e
        import boto3
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def name(self) -> str:
        return "s3_compatible"

    def prepare_upload(self, *, key: str, mime: str, byte_size: int, ttl_minutes: int = 15) -> UploadIntent:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": mime},
            ExpiresIn=ttl_minutes * 60,
        )
        return UploadIntent(
            media_id=secrets.token_urlsafe(12),
            upload_url=url,
            upload_method="PUT",
            public_url=self.public_url_for(key),
            storage_key=key,
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat(),
        )

    def public_url_for(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    async def delete(self, key: str) -> None:
        # boto3 client.delete_object is sync; wrap if it becomes a bottleneck.
        self._client.delete_object(Bucket=self.bucket, Key=key)


# ---------- Factory ---------------------------------------------------------

_provider: Optional[StorageProvider] = None


def get_provider() -> StorageProvider:
    global _provider
    if _provider is not None:
        return _provider
    kind = (os.environ.get("STORAGE_PROVIDER") or "").lower()
    if kind in ("r2", "s3", "s3_compatible"):
        try:
            _provider = S3CompatibleStorage(
                endpoint_url=os.environ["STORAGE_ENDPOINT_URL"],
                region=os.environ.get("STORAGE_REGION", "auto"),
                access_key=os.environ["STORAGE_ACCESS_KEY_ID"],
                secret_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
                bucket=os.environ["STORAGE_BUCKET"],
                public_base_url=os.environ["STORAGE_PUBLIC_BASE_URL"],
            )
            logger.info("Storage provider: %s (bucket=%s)", _provider.name(), _provider.bucket)
            return _provider
        except Exception:
            logger.exception("Failed to initialise %s storage; falling back to local dev stub", kind)
    _provider = LocalDevStorage()
    logger.info("Storage provider: %s", _provider.name())
    return _provider


def reset_provider_for_tests() -> None:
    """Clear the cached provider so a fresh `get_provider()` re-reads env.
    Production code should never call this.
    """
    global _provider
    _provider = None


# ---------- High-level helpers used by routes -------------------------------

def build_key(tenant_id: str, kind: MediaKind, subject_id: Optional[str], filename: str,
              barn_id: str = "primary") -> str:
    """Stable, namespaced storage key. Never leak DB primary keys directly.

    Phase 4B-7: keys are namespaced by ``barn_id`` first so media is partitioned
    per barn at the object-store level (forward-compatible — no live callers yet).
    """
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")[-64:] or "file"
    when = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    nonce = secrets.token_urlsafe(8)
    parts = [barn_id, tenant_id, kind, when]
    if subject_id:
        parts.append(subject_id)
    parts.append(f"{nonce}-{safe_filename}")
    return "/".join(parts)


def validate_upload(kind: MediaKind, mime: str, byte_size: int) -> None:
    from fastapi import HTTPException
    if kind not in ALLOWED_MIME:
        raise HTTPException(400, f"Unknown media kind: {kind}")
    if mime not in ALLOWED_MIME[kind]:
        raise HTTPException(400, f"Mime type {mime} not allowed for {kind}")
    if byte_size <= 0 or byte_size > MAX_BYTES[kind]:
        raise HTTPException(400, f"Size out of bounds for {kind} (max {MAX_BYTES[kind]} bytes)")


async def ensure_media_indexes(db):
    await db.media.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.media.create_index([("linked_horse_ids", 1)])
    await db.media.create_index([("linked_task_id", 1)])
    await db.media.create_index([("committed", 1)])
