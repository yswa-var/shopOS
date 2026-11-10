from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shopos.audit import record_event
from shopos.auth import CurrentUser, Db, require_permission
from shopos.models import Bill, ProofAttachment, User
from shopos.storage import SIGNED_URL_SECONDS, S3Storage, StorageUnavailable, get_storage

router = APIRouter(prefix="/attachments/proofs", tags=["proof attachments"])
CanWrite = Annotated[User, Depends(require_permission("attachments:write"))]
Storage = Annotated[S3Storage, Depends(get_storage)]


class InitiateProof(BaseModel):
    client_upload_id: UUID
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(ge=1, le=15_000_000)


class InitiatedProof(BaseModel):
    id: UUID
    status: str
    upload_url: str | None
    required_headers: dict[str, str]
    expires_in_seconds: int | None


class ProofInfo(BaseModel):
    id: UUID
    status: str
    content_type: str
    size_bytes: int


class DownloadProof(BaseModel):
    download_url: str
    expires_in_seconds: int


def storage_error(exc: StorageUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail="Storage unavailable")


def ensure_access(attachment: ProofAttachment, user: User) -> None:
    if user.role != "owner" and attachment.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Attachment access denied")


def ensure_read_access(db: Db, attachment: ProofAttachment, user: User) -> None:
    if user.role == "owner":
        return
    granted = {entry.permission for entry in user.permissions}
    linked = db.scalar(select(Bill.id).where(Bill.proof_attachment_id == attachment.id)) is not None
    if linked and "bills:read" in granted:
        return
    if not linked and attachment.uploaded_by == user.id and "attachments:read" in granted:
        return
    raise HTTPException(status_code=403, detail="Attachment access denied")


def valid_image_header(content_type: str, header: bytes) -> bool:
    if content_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def initiated_response(attachment: ProofAttachment, storage: S3Storage) -> InitiatedProof:
    if attachment.status == "ready":
        return InitiatedProof(id=attachment.id, status="ready", upload_url=None, required_headers={}, expires_in_seconds=None)
    try:
        url = storage.upload_url(attachment.upload_key, attachment.content_type)
    except StorageUnavailable as exc:
        raise storage_error(exc) from exc
    return InitiatedProof(
        id=attachment.id,
        status="pending",
        upload_url=url,
        required_headers={"Content-Type": attachment.content_type},
        expires_in_seconds=SIGNED_URL_SECONDS,
    )


def existing_upload(db: Db, user_id: UUID, payload: InitiateProof) -> ProofAttachment | None:
    attachment = db.scalar(select(ProofAttachment).where(ProofAttachment.uploaded_by == user_id, ProofAttachment.client_upload_id == payload.client_upload_id))
    if attachment is not None and (attachment.content_type != payload.content_type or attachment.size_bytes != payload.size_bytes):
        raise HTTPException(status_code=409, detail="Upload ID already used with different metadata")
    return attachment


@router.post("/initiate", response_model=InitiatedProof)
def initiate(payload: InitiateProof, db: Db, user: CurrentUser, _access: CanWrite, storage: Storage) -> InitiatedProof:
    attachment = existing_upload(db, user.id, payload)
    if attachment is not None:
        return initiated_response(attachment, storage)
    identifier = uuid4()
    attachment = ProofAttachment(
        id=identifier,
        client_upload_id=payload.client_upload_id,
        uploaded_by=user.id,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        upload_key=f"pending/{identifier}",
        object_key=f"proofs/{identifier}",
        status="pending",
    )
    db.add(attachment)
    response = initiated_response(attachment, storage)
    record_event(db, actor_id=user.id, action="proof.initiate", target_type="proof", target_id=identifier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        attachment = existing_upload(db, user.id, payload)
        if attachment is None:
            raise
        return initiated_response(attachment, storage)
    return response


@router.post("/{attachment_id}/complete", response_model=ProofInfo)
def complete(attachment_id: UUID, db: Db, user: CurrentUser, _access: CanWrite, storage: Storage) -> ProofInfo:
    attachment = db.scalar(select(ProofAttachment).where(ProofAttachment.id == attachment_id).with_for_update())
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ensure_access(attachment, user)
    if attachment.status == "ready":
        return proof_info(attachment)
    try:
        metadata = storage.head(attachment.upload_key)
        if metadata is None:
            raise HTTPException(status_code=409, detail="Upload has not reached storage; retry the upload")
        if metadata.size_bytes != attachment.size_bytes or metadata.content_type != attachment.content_type:
            raise HTTPException(status_code=409, detail="Uploaded size or type differs; retry the upload")
        if not valid_image_header(attachment.content_type, storage.first_bytes(attachment.upload_key)):
            raise HTTPException(status_code=422, detail="Uploaded file is not a supported image")
        storage.promote(attachment.upload_key, attachment.object_key)
        final = storage.head(attachment.object_key)
        if final is None or final.size_bytes != attachment.size_bytes or final.content_type != attachment.content_type:
            raise HTTPException(status_code=409, detail="Copied proof differs; retry completion")
        if not valid_image_header(attachment.content_type, storage.first_bytes(attachment.object_key)):
            raise HTTPException(status_code=409, detail="Copied proof differs; retry completion")
    except StorageUnavailable as exc:
        raise storage_error(exc) from exc
    attachment.status = "ready"
    attachment.ready_at = datetime.now(timezone.utc)
    record_event(db, actor_id=user.id, action="proof.complete", target_type="proof", target_id=attachment.id)
    db.commit()
    try:
        storage.delete(attachment.upload_key)
    except StorageUnavailable:
        # The final key is private and immutable through the temporary signed URL.
        pass
    else:
        attachment.temp_deleted_at = datetime.now(timezone.utc)
        db.commit()
    return proof_info(attachment)


def proof_info(attachment: ProofAttachment) -> ProofInfo:
    return ProofInfo(id=attachment.id, status=attachment.status, content_type=attachment.content_type, size_bytes=attachment.size_bytes)


@router.get("/{attachment_id}", response_model=ProofInfo)
def get_proof(attachment_id: UUID, db: Db, user: CurrentUser) -> ProofInfo:
    attachment = db.get(ProofAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ensure_read_access(db, attachment, user)
    return proof_info(attachment)


@router.get("/{attachment_id}/download", response_model=DownloadProof)
def download(attachment_id: UUID, db: Db, user: CurrentUser, storage: Storage) -> DownloadProof:
    attachment = db.get(ProofAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ensure_read_access(db, attachment, user)
    if attachment.status != "ready":
        raise HTTPException(status_code=409, detail="Attachment upload is incomplete")
    try:
        url = storage.download_url(attachment.object_key)
    except StorageUnavailable as exc:
        raise storage_error(exc) from exc
    record_event(db, actor_id=user.id, action="proof.download_url", target_type="proof", target_id=attachment.id)
    db.commit()
    return DownloadProof(download_url=url, expires_in_seconds=SIGNED_URL_SECONDS)
