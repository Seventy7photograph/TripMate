# 文件说明：业务服务：upload_service。
import asyncio
import hashlib
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.uploaded_asset import UploadedAsset
from app.schemas.upload import UploadedAssetResponse

_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}


class UploadError(Exception):
    code = "upload_error"


class UploadTooLarge(UploadError):
    code = "upload_too_large"


class UnsupportedUpload(UploadError):
    code = "unsupported_upload_type"


class InvalidUpload(UploadError):
    code = "invalid_upload_content"


class UploadNotFound(UploadError):
    code = "upload_not_found"


@dataclass(frozen=True, slots=True)
class UploadContext:
    documents: list[tuple[str, str]]
    image_data_urls: list[str]
    assets: list[UploadedAsset]


class UploadService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._root = settings.upload_dir.resolve()

    async def create(
        self,
        *,
        owner_id: UUID,
        upload: UploadFile,
    ) -> UploadedAssetResponse:
        max_read = max(
            self._settings.max_image_upload_bytes,
            self._settings.max_document_upload_bytes,
        )
        # 多读一个字节即可在完整缓冲前识别超限文件。
        data = await upload.read(max_read + 1)
        if len(data) > max_read:
            raise UploadTooLarge

        name = self._safe_name(upload.filename)
        # 以真实内容检测结果为准，不能只相信浏览器提供的 MIME。
        mime_type, kind, extracted_text, data = self._inspect(
            data=data,
            name=name,
            reported_mime=upload.content_type or "",
        )
        storage_key = uuid4().hex
        owner_dir = self._root / str(owner_id)
        path = owner_dir / f"{storage_key}.bin"
        owner_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

        now = datetime.now(UTC)
        model = UploadedAsset(
            owner_id=owner_id,
            original_name=name,
            storage_key=storage_key,
            mime_type=mime_type,
            kind=kind,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            extracted_text=extracted_text,
            status="ready",
            created_at=now,
            expires_at=now + timedelta(hours=self._settings.upload_ttl_hours),
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
            await self._session.commit()
        except Exception:
            # 数据库写入失败时清理已落盘文件，保持两侧状态一致。
            path.unlink(missing_ok=True)
            raise
        return self._response(model)

    async def get_owned(
        self,
        *,
        owner_id: UUID,
        asset_id: UUID,
    ) -> UploadedAsset:
        model = await self._session.scalar(
            select(UploadedAsset).where(
                UploadedAsset.id == asset_id,
                UploadedAsset.owner_id == owner_id,
                UploadedAsset.status == "ready",
            )
        )
        if model is None or model.expires_at <= datetime.now(UTC):
            raise UploadNotFound
        return model

    async def read_content(self, asset: UploadedAsset) -> bytes:
        path = self._path(asset)
        if not path.is_file():
            raise UploadNotFound
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, *, owner_id: UUID, asset_id: UUID) -> None:
        asset = await self.get_owned(owner_id=owner_id, asset_id=asset_id)
        path = self._path(asset)
        await self._session.delete(asset)
        await self._session.commit()
        path.unlink(missing_ok=True)

    async def context_for_message(
        self,
        *,
        owner_id: UUID,
        asset_ids: list[UUID],
    ) -> UploadContext:
        if len(asset_ids) > self._settings.max_uploads_per_message:
            raise UploadTooLarge
        assets: list[UploadedAsset] = []
        for asset_id in asset_ids:
            assets.append(await self.get_owned(owner_id=owner_id, asset_id=asset_id))

        documents: list[tuple[str, str]] = []
        image_data_urls: list[str] = []
        for asset in assets:
            if asset.kind == "image":
                image_data_urls.append(
                    f"data:{asset.mime_type};base64,"
                    f"{self._base64(await self.read_content(asset))}"
                )
            elif asset.extracted_text:
                documents.append((asset.original_name, asset.extracted_text))
        return UploadContext(
            documents=documents,
            image_data_urls=image_data_urls,
            assets=assets,
        )

    def _inspect(
        self,
        *,
        data: bytes,
        name: str,
        reported_mime: str,
    ) -> tuple[str, str, str | None, bytes]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    image_format = image.format
                    width, height = image.size
                    image.verify()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            image_format = None
            width = height = 0
        if image_format in _IMAGE_FORMATS:
            if len(data) > self._settings.max_image_upload_bytes:
                raise UploadTooLarge
            if width * height > self._settings.max_image_pixels:
                raise InvalidUpload
            return self._normalize_image(data, width, height)
        if reported_mime.startswith("image/"):
            raise InvalidUpload

        if data.startswith(b"%PDF-"):
            if len(data) > self._settings.max_document_upload_bytes:
                raise UploadTooLarge
            return "application/pdf", "document", self._extract_pdf(data), data

        suffix = Path(name).suffix.lower()
        if suffix in _TEXT_SUFFIXES or reported_mime in {
            "text/plain",
            "text/markdown",
        }:
            if len(data) > self._settings.max_document_upload_bytes:
                raise UploadTooLarge
            text = self._extract_text(data)
            return "text/plain", "document", text, data

        raise UnsupportedUpload

    def _normalize_image(
        self,
        data: bytes,
        width: int,
        height: int,
    ) -> tuple[str, str, str | None, bytes]:
        if (
            width <= self._settings.max_image_dimension
            and height <= self._settings.max_image_dimension
        ):
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
            mime_type, _ = _IMAGE_FORMATS[image_format]  # type: ignore[index]
            return mime_type, "image", None, data

        with Image.open(BytesIO(data)) as image:
            image.thumbnail(
                (
                    self._settings.max_image_dimension,
                    self._settings.max_image_dimension,
                ),
                Image.Resampling.LANCZOS,
            )
            normalized_image = (
                image.convert("RGB")
                if image.mode not in {"RGB", "RGBA"}
                else image
            )
            output = BytesIO()
            normalized_image.save(output, format="WEBP", quality=85, method=6)
        normalized = output.getvalue()
        if len(normalized) > self._settings.max_image_upload_bytes:
            raise UploadTooLarge
        return "image/webp", "image", None, normalized

    def _extract_pdf(self, data: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise InvalidUpload
            if len(reader.pages) > 40:
                raise InvalidUpload
            parts = [page.extract_text() or "" for page in reader.pages]
        except InvalidUpload:
            raise
        except Exception as exc:
            raise InvalidUpload from exc
        return self._truncate("\n".join(parts).strip())

    def _extract_text(self, data: bytes) -> str:
        if b"\x00" in data:
            raise InvalidUpload
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidUpload from exc
        return self._truncate(text.strip())

    def _truncate(self, text: str) -> str:
        return text[: self._settings.max_extracted_text_chars]

    def _path(self, asset: UploadedAsset) -> Path:
        # 解析并校验目录包含关系，防止存储键造成路径穿越。
        path = (self._root / str(asset.owner_id) / f"{asset.storage_key}.bin").resolve()
        if self._root not in path.parents:
            raise UploadNotFound
        return path

    @staticmethod
    def _safe_name(name: str | None) -> str:
        raw = Path(name or "upload").name
        cleaned = "".join(
            character
            for character in raw
            if character.isprintable()
            and character not in {"/", "\\", "<", ">", '"', "'"}
        ).strip()
        return (cleaned or "upload")[:255]

    @staticmethod
    def _base64(data: bytes) -> str:
        import base64

        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _response(asset: UploadedAsset) -> UploadedAssetResponse:
        return UploadedAssetResponse(
            id=asset.id,
            name=asset.original_name,
            mime_type=asset.mime_type,
            kind=asset.kind,  # type: ignore[arg-type]
            size_bytes=asset.size_bytes,
            created_at=asset.created_at,
            expires_at=asset.expires_at,
        )
