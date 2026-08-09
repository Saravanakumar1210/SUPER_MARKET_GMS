"""Cloudinary image upload helpers."""

from __future__ import annotations

import io
import re
import uuid
from pathlib import Path

import cloudinary
import cloudinary.uploader
from PIL import Image

from app.config import get_settings

MAX_UPLOAD_BYTES = 9_500_000
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def configure_cloudinary() -> None:
    settings = get_settings()
    if not settings.cloudinary_configured:
        raise RuntimeError("Cloudinary is not configured — set CLOUDINARY_* in .env")
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def public_id_from_url(url: str) -> str | None:
    if "res.cloudinary.com" not in url:
        return None
    match = re.search(r"/upload/(?:v\d+/)?(.+)$", url)
    if not match:
        return None
    return match.group(1).rsplit(".", 1)[0]


def _compress_if_needed(data: bytes, ext: str) -> bytes:
    if len(data) <= MAX_UPLOAD_BYTES:
        return data
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        save_fmt = "JPEG"
        out_ext = ".jpg"
    else:
        save_fmt = ext.lstrip(".").upper()
        if save_fmt == "JPG":
            save_fmt = "JPEG"
        out_ext = ext
    quality = 85
    while quality >= 50:
        buf = io.BytesIO()
        img.save(buf, format=save_fmt, quality=quality, optimize=True)
        compressed = buf.getvalue()
        if len(compressed) <= MAX_UPLOAD_BYTES:
            return compressed
        quality -= 10
        if img.width > 1800:
            ratio = 1800 / img.width
            img = img.resize((1800, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
    return compressed


def upload_bytes(
    data: bytes,
    *,
    folder: str,
    public_id: str,
    ext: str = ".jpg",
    asset_folder: str | None = None,
) -> dict:
    configure_cloudinary()
    payload = _compress_if_needed(data, ext)
    resource_type = "image"
    options: dict = {
        "folder": folder,
        "public_id": public_id,
        "overwrite": True,
        "resource_type": resource_type,
    }
    if asset_folder:
        options["asset_folder"] = asset_folder
    return cloudinary.uploader.upload(payload, **options)


def upload_file_path(path: Path, *, asset_key: str, folder: str) -> dict:
    ext = path.suffix.lower()
    if ext not in IMAGE_EXTS:
        raise ValueError(f"Unsupported image type: {ext}")
    public_id = Path(asset_key).stem
    subfolder = str(Path(asset_key).parent).replace("\\", "/")
    if subfolder and subfolder != ".":
        full_folder = f"{folder}/{subfolder}"
        asset_folder = full_folder
    else:
        full_folder = folder
        asset_folder = folder
    data = path.read_bytes()
    return upload_bytes(
        data,
        folder=full_folder,
        public_id=public_id,
        ext=ext,
        asset_folder=asset_folder,
    )


def upload_upload_file(data: bytes, filename: str, *, subfolder: str) -> dict:
    settings = get_settings()
    ext = Path(filename).suffix.lower() or ".jpg"
    if ext not in IMAGE_EXTS:
        raise ValueError(f"Unsupported file type: {ext}")
    public_id = f"{Path(filename).stem}_{uuid.uuid4().hex[:8]}"
    folder = f"{settings.cloudinary_folder}/{subfolder}"
    return upload_bytes(data, folder=folder, public_id=public_id, ext=ext)


def delete_by_url(url: str) -> None:
    public_id = public_id_from_url(url)
    if not public_id:
        return
    configure_cloudinary()
    cloudinary.uploader.destroy(public_id, resource_type="image")
