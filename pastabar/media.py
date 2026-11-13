"""Media files live outside the frontend build and survive deployments."""

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4


class MediaRepository:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.settings_path = directory / "banner.json"

    def banner(self):
        try:
            return json.loads(self.settings_path.read_text()).get("video_url")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_image(self, data: bytes) -> str:
        from io import BytesIO

        from PIL import Image, UnidentifiedImageError

        if not data or len(data) > 8 * 1024 * 1024:
            raise ValueError("Image must be between 1 byte and 8 MB")
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}.get(image.format)
                if not extension:
                    raise ValueError("Unsupported image format")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValueError("Invalid image") from None
        name = f"dish_upload_{uuid4().hex}.{extension}"
        (self.directory / name).write_bytes(data)
        return f"/uploads/{name}"

    def set_banner(self, url: str | None):
        old = self.banner()
        fd, name = tempfile.mkstemp(dir=self.directory, prefix=".banner-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"video_url": url}, stream)
            os.replace(name, self.settings_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        if old and old != url and old.startswith(("/uploads/banner_", "/static/images/banner_")):
            (self.directory / Path(old).name).unlink(missing_ok=True)
