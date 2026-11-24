"""Local-disk document storage. In production swap the two functions for S3 with server-side encryption and signed URLs."""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import Unprocessable

SIGNATURES = {"application/pdf": b"%PDF", "image/png": b"\x89PNG", "image/jpeg": b"\xff\xd8\xff"}
EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


def save_upload(owner_id: uuid.UUID, file: UploadFile) -> tuple[str, int, str]:
    s = get_settings()
    data = file.file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise Unprocessable(f"Files must be {s.max_upload_bytes // (1024 * 1024)}MB or smaller.", code="file_too_large")
    ctype = file.content_type or ""
    sig = SIGNATURES.get(ctype)
    if sig is None or not data.startswith(sig):
        raise Unprocessable("Upload a PDF, PNG or JPEG file.", code="bad_file_type")
    key = f"{owner_id}/{uuid.uuid4().hex}{EXT[ctype]}"
    path = Path(s.storage_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key, len(data), ctype


def read_file(key: str) -> bytes:
    root = Path(get_settings().storage_dir).resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise Unprocessable("Invalid file reference.")
    return path.read_bytes()


def delete_file(key: str) -> None:
    root = Path(get_settings().storage_dir).resolve()
    path = (root / key).resolve()
    if root in path.parents and path.exists():
        path.unlink()
