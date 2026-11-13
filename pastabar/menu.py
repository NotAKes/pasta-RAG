"""Validated menu storage with stable IDs and atomic replacement."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


class MenuRepository:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    @staticmethod
    def normalize(data: list[dict]) -> list[dict]:
        if not isinstance(data, list) or not data:
            raise ValueError("Menu must be a non-empty JSON array")
        normalized = copy.deepcopy(data)
        ids = set()
        for item in normalized:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise ValueError("Each entry requires text and metadata")
            meta = item.get("metadata")
            if not isinstance(meta, dict) or not isinstance(meta.get("categories"), list):
                raise ValueError("Each entry requires metadata.categories")
            if not all(isinstance(c, str) for c in meta["categories"]):
                raise ValueError("Categories must be strings")
            is_info = "info" in meta["categories"]
            if not is_info:
                if not isinstance(meta.get("dish_name"), str) or not meta["dish_name"].strip():
                    raise ValueError("Each dish requires a name")
                try:
                    price = Decimal(str(meta["price"]))
                    if not price.is_finite() or price < 0 or price > 1_000_000:
                        raise ValueError("Price must be between 0 and 1000000 PHP")
                    if price != price.quantize(Decimal("0.01")):
                        raise ValueError("Prices support at most two decimal places")
                except (KeyError, InvalidOperation):
                    raise ValueError("Each dish requires a valid price") from None
            identity = f"{meta.get('dish_name', 'info')}:{item['text']}"
            item.setdefault("id", str(uuid5(NAMESPACE_URL, f"pastabar:{identity}")))
            if not isinstance(item["id"], str) or not item["id"] or len(item["id"]) > 100:
                raise ValueError("Entry ID must be a non-empty string of at most 100 characters")
            if item["id"] in ids:
                raise ValueError("Duplicate menu ID; assign explicit unique IDs to duplicate names")
            ids.add(item["id"])
        return normalized

    def all_items(self) -> list[dict]:
        with self._lock:
            return self.normalize(json.loads(self.path.read_text(encoding="utf-8")))

    def public_items(self) -> list[dict]:
        return [item for item in self.all_items() if "info" not in item["metadata"]["categories"]]

    def fingerprint(self) -> str:
        content = json.dumps(self.all_items(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def save(self, data: list[dict]) -> int:
        normalized = self.normalize(data)
        payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".menu-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        return len(normalized)

    def migrate_ids(self) -> None:
        """Persist generated IDs once so renames/reordering do not change identity."""
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if any("id" not in item for item in raw):
            self.save(raw)
