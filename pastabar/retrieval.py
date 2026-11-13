"""Lazy semantic retrieval with deterministic menu filtering and offline fallback."""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import threading
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, uuid5

if TYPE_CHECKING:
    from .config import Settings
    from .menu import MenuRepository

logger = logging.getLogger(__name__)
MAX_CONTEXT = 18_000

# Dietary categories deliberately use separate expressions: vegetarian is not vegan.
_CATEGORY_PATTERNS = (
    ("vegan", r"\bvegan\w*\b|\bвеган\w*"),
    ("vegetarian", r"\bvegetarian\w*\b|\bвегетариан\w*"),
    ("address", r"\b(address|location|located|directions)\b|\bwhere are you\b|\bадрес\w*|\bгде (вы|находит)"),
    (
        "hours",
        r"\b(hours|opening|closing|open|close)\b|\bчас\w*|\bграфик\w*|\bрежим\w*|\bкогда (откры|закры)|\bдо скольки",
    ),
    ("reservations", r"\b(reserv\w*|book\w*)\b|\bброн\w*|\bзаброни\w*"),
    ("contacts", r"\b(contact\w*|manager|phone)\b|\bконтакт\w*|\bменеджер\w*|\bтелефон\w*"),
    ("breakfast", r"\bbreakfast\w*\b|\bзавтрак\w*"),
    ("crepe", r"\b(crepes?|pancakes?)\b|\bблин\w*|\bблинчик\w*"),
    ("pasta", r"\b(pasta|spaghetti|fettuccine)\b|\bпаст[ауыое]\b|\bспагетти\b|\bфетуч\w*"),
    ("info", r"\b(information|info)\b|\bинформац\w*"),
)
_INFO_TAGS = {
    "address": {"address", "location"},
    "hours": {"time", "hours", "opening hours"},
    "reservations": {"reservation", "reservations", "table", "бронирование"},
    "contacts": {"contacts", "contact", "manager"},
    "info": {"info"},
}


def _categories(query: str) -> list[str]:
    return [name for name, pattern in _CATEGORY_PATTERNS if re.search(pattern, query.casefold())]


def select_category(query: str) -> str | None:
    """Return the highest-priority explicit category, without loading ML libraries."""
    categories = _categories(query)
    return categories[0] if categories else None


def _tags(item: dict) -> set[str]:
    metadata = item.get("metadata") or {}
    values = metadata.get("categories", [])
    if isinstance(values, str):
        values = [values]
    return {str(value).casefold() for value in values}


def _matching(items: list[dict], categories: list[str]) -> list[dict]:
    info = [name for name in categories if name in _INFO_TAGS]
    if info:
        tags = set().union(*(_INFO_TAGS[name] for name in info))
        return [item for item in items if _tags(item) & tags]
    required = set(categories)
    result = []
    for item in items:
        tags = _tags(item)
        if "vegan" in tags:
            tags = tags | {"vegetarian"}
        if "pancakes" in tags or "sweet_crepe" in tags or "savoury_crepe" in tags:
            tags = tags | {"crepe"}
        if required <= tags:
            result.append(item)
    return result


def _render(items: list[dict]) -> str:
    parts = []
    seen = set()
    for item in items:
        text = str(item.get("text", "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        label = "INFO" if "info" in _tags(item) else "MENU ITEM"
        metadata = item.get("metadata") or {}
        if label == "MENU ITEM" and "price" in metadata:
            # Legacy descriptions embed prices. Metadata is the source of truth
            # after admin edits; do not expose conflicting stale amounts to the LLM.
            text = re.sub(r"(?i)(?:price|цена)\s*:\s*[\d,.]+\s*(?:PHP|₱)?[.]?", "", text)
            text += f"\nCurrent price: {metadata['price']} PHP."
        parts.append(f"[{label}] {text}")
    context = "\n---\n".join(parts)
    if not context:
        return "NO_CONTEXT: No matching information was retrieved; this does not prove absence from the menu."
    if len(context) > MAX_CONTEXT:
        marker = "\n[CONTEXT TRUNCATED: additional matches may exist]"
        return context[: MAX_CONTEXT - len(marker)] + marker
    return context


def _effective_query(query: str, history: list[dict] | None) -> str:
    # Resolve short follow-ups without letting a previous category override a new request.
    followup = r"\b(it|that|those|them|these|price|ingredients)\b|how much|\b(это|этого|них|они|сколько|состав|цена)\b"
    if not select_category(query) and history and re.search(followup, query.casefold()):
        for message in reversed(history[-8:]):
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                return f"{message['content']}\n{query}"
    return query


def _lexical(items: list[dict], query: str) -> list[dict]:
    stopwords = {
        "what",
        "with",
        "have",
        "your",
        "this",
        "that",
        "there",
        "please",
        "есть",
        "меня",
        "какие",
        "хочу",
        "можно",
        "вас",
    }
    tokens = {word for word in re.findall(r"\w+", query.casefold()) if len(word) > 2 and word not in stopwords}
    scored = []
    for index, item in enumerate(items):
        text = str(item.get("text", "")).casefold()
        words = set(re.findall(r"\w+", text)) | _tags(item)
        score = len(tokens & words)
        if score:
            scored.append((-score, index, item))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in scored[:8]]


class RetrievalService:
    """Own the optional model/index; ordinary content changes never delete collections."""

    def __init__(self, menu: MenuRepository, settings: Settings) -> None:
        self.menu = menu
        self.settings = settings
        self._lock = threading.RLock()
        self._model: Any = None
        self._client: Any = None
        self._models: Any = None
        self._fingerprint: str | None = None
        self._status = "not_started"
        self._startup_task: asyncio.Task | None = None
        self._closed = False

    @property
    def status(self) -> str:
        return self._status

    async def start(self) -> None:
        """Schedule model loading in a worker, returning without waiting for a download."""
        if self._closed or self._startup_task is not None:
            return
        self._status = "loading"
        self._startup_task = asyncio.create_task(asyncio.to_thread(self._initialize))

    def _snapshot(self) -> tuple[list[dict], str]:
        # Re-read if a repository replacement happened between the two calls.
        for _ in range(3):
            fingerprint = self.menu.fingerprint()
            items = copy.deepcopy(self.menu.all_items())
            if fingerprint == self.menu.fingerprint():
                return items, fingerprint
        raise RuntimeError("Menu is changing too quickly to take a consistent snapshot")

    def _initialize(self) -> None:
        client = None
        try:
            from qdrant_client import QdrantClient, models
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(
                self.settings.embedding_model,
                cache_folder=str(self.settings.model_cache_dir),
                device="cpu",
            )
            client = QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_key,
                timeout=10,
            )
            with self._lock:
                if self._closed:
                    client.close()
                    return
                self._model, self._client, self._models = model, client, models
                items, fingerprint = self._snapshot()
                self._sync(items, fingerprint)
                self._status = "ready"
        except Exception:
            logger.warning("Semantic retrieval unavailable; using lexical menu retrieval", exc_info=True)
            with self._lock:
                if not self._closed:
                    self._status = "degraded"
                self._model = None
                self._client = None
            if client is not None:
                try:
                    client.close()
                except Exception:
                    logger.debug("Failed to close unavailable Qdrant client", exc_info=True)

    @staticmethod
    def _point_id(item: dict) -> str:
        return str(uuid5(NAMESPACE_URL, f"pastabar:menu:{item['id']}"))

    def _sync(self, items: list[dict], fingerprint: str) -> None:
        if self._fingerprint == fingerprint:
            return
        client, models = self._client, self._models
        collection = self.settings.qdrant_collection
        dimension = self._model.get_sentence_embedding_dimension()
        if not dimension:
            dimension = len(self._model.encode("dimension probe"))
        if not client.collection_exists(collection_name=collection):
            client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=int(dimension), distance=models.Distance.COSINE),
            )
        else:
            vectors = client.get_collection(collection_name=collection).config.params.vectors
            if isinstance(vectors, dict) or vectors.size != dimension:
                raise RuntimeError(
                    "Embedding dimensions differ; explicitly migrate the collection or choose a new name"
                )

        existing: dict[str, dict] = {}
        remote_ids: dict[str, Any] = {}
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                existing[str(point.id)] = point.payload or {}
                remote_ids[str(point.id)] = point.id
            if offset is None:
                break
        current_ids = {self._point_id(item) for item in items}
        if set(existing) == current_ids and all(
            payload.get("_menu_hash") == fingerprint for payload in existing.values()
        ):
            self._fingerprint = fingerprint
            return

        # All points carry the version. Interrupted writes cannot masquerade as a full sync.
        for start in range(0, len(items), 64):
            batch = items[start : start + 64]
            encoded = self._model.encode([str(item.get("text", "")) for item in batch])
            points = []
            for item, vector in zip(batch, encoded):
                if hasattr(vector, "tolist"):
                    vector = vector.tolist()
                points.append(
                    models.PointStruct(
                        id=self._point_id(item),
                        vector=vector,
                        payload={
                            "id": item["id"],
                            "text": item.get("text", ""),
                            "metadata": item.get("metadata", {}),
                            "_menu_hash": fingerprint,
                        },
                    )
                )
            client.upsert(collection_name=collection, points=points, wait=True)
        stale = [remote_ids[id_] for id_ in set(existing) - current_ids]
        if stale:
            client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=stale),
                wait=True,
            )
        self._fingerprint = fingerprint

    async def search(self, query: str, history: list[dict] | None = None) -> str:
        """Retrieve current raw menu facts, falling back safely when ML is unavailable."""
        return await asyncio.to_thread(self._search, query, history)

    def _search(self, query: str, history: list[dict] | None) -> str:
        with self._lock:
            if self._closed:
                return "NO_CONTEXT: Retrieval is closed."
            items, fingerprint = self._snapshot()
            query = _effective_query(query, history)
            categories = _categories(query)
            if categories:
                return _render(_matching(items, categories))
            if self._model is not None and self._client is not None:
                try:
                    self._sync(items, fingerprint)
                    vector = self._model.encode(query)
                    if hasattr(vector, "tolist"):
                        vector = vector.tolist()
                    response = self._client.query_points(
                        collection_name=self.settings.qdrant_collection,
                        query=vector,
                        limit=8,
                        with_payload=True,
                        score_threshold=0.35,
                    )
                    self._status = "ready"
                    # Use repository payloads, never stale remote text.
                    by_id = {str(item["id"]): item for item in items}
                    matches = [
                        by_id[str(hit.payload["id"])]
                        for hit in response.points
                        if hit.payload and str(hit.payload.get("id")) in by_id
                    ]
                    if matches:
                        return _render(matches)
                except Exception:
                    self._status = "degraded"
                    logger.warning("Vector retrieval failed; using lexical fallback", exc_info=True)
            return _render(_lexical(items, query))

    async def close(self) -> None:
        """Wait for any loader before releasing its client (worker threads are not cancelled)."""
        self._closed = True
        if self._startup_task is not None:
            await asyncio.shield(self._startup_task)
        await asyncio.to_thread(self._close)

    def _close(self) -> None:
        with self._lock:
            try:
                if self._client is not None:
                    self._client.close()
            finally:
                self._client = self._model = None
                self._status = "closed"
