"""Service contracts run without transformers, Qdrant, or provider credentials."""

import asyncio
import hashlib
import importlib
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pastabar.assistant import AssistantService
from pastabar.retrieval import MAX_CONTEXT, RetrievalService, select_category


class Menu:
    def __init__(self, items):
        self.items = items

    def all_items(self):
        return self.items

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.items, sort_keys=True).encode()).hexdigest()


def settings():
    return SimpleNamespace(
        qdrant_url="http://example.invalid:6333",
        qdrant_key="secret",
        qdrant_collection="test-menu",
        embedding_model="test-model",
        model_cache_dir=Path("/tmp/model-test"),
        deepseek_key="",
        deepseek_model="deepseek-chat",
        manager_contact="@manager",
    )


def item(id_, text, *categories):
    return {"id": id_, "text": text, "metadata": {"categories": list(categories)}}


class FakeModel:
    def __init__(self):
        self.calls = 0
        self.active = 0
        self.max_active = 0

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, text):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        time.sleep(0.002)
        self.active -= 1
        return [[1.0, 0.0, 0.0] for _ in text] if isinstance(text, list) else [1.0, 0.0, 0.0]


class Record:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeClient:
    def __init__(self):
        self.points = {}
        self.exists = False
        self.size = 3
        self.upserts = 0
        self.deleted = []
        self.closed = False

    def collection_exists(self, **kwargs):
        return self.exists

    def create_collection(self, **kwargs):
        self.exists = True
        self.size = kwargs["vectors_config"].size

    def get_collection(self, **kwargs):
        return Record(config=Record(params=Record(vectors=Record(size=self.size))))

    def scroll(self, **kwargs):
        return list(self.points.values()), None

    def upsert(self, **kwargs):
        self.upserts += 1
        for point in kwargs["points"]:
            self.points[point.id] = point

    def delete(self, **kwargs):
        for id_ in kwargs["points_selector"].points:
            self.deleted.append(id_)
            self.points.pop(id_, None)

    def query_points(self, **kwargs):
        return Record(points=list(self.points.values()))

    def close(self):
        self.closed = True


MODELS = SimpleNamespace(
    VectorParams=Record, Distance=SimpleNamespace(COSINE="Cosine"), PointStruct=Record, PointIdsList=Record
)


def semantic_service(menu):
    service = RetrievalService(menu, settings())
    service._client = FakeClient()
    service._model = FakeModel()
    service._models = MODELS
    return service


class CategoryTests(unittest.TestCase):
    def test_categories_are_bilingual_and_diet_specific(self):
        pairs = {
            "vegan food": "vegan",
            "веганское": "vegan",
            "вегетарианское": "vegetarian",
            "vegetarian breakfast": "vegetarian",
            "блины": "crepe",
            "breakfast": "breakfast",
            "паста": "pasta",
            "где вы?": "address",
            "opening hours": "hours",
            "бронирование": "reservations",
            "hello": None,
        }
        for query, expected in pairs.items():
            with self.subTest(query=query):
                self.assertEqual(select_category(query), expected)

    def test_imports_do_not_require_optional_dependencies(self):
        with patch.dict(sys.modules, {"sentence_transformers": None, "qdrant_client": None, "openai": None}):
            importlib.reload(importlib.import_module("pastabar.retrieval"))
            importlib.reload(importlib.import_module("pastabar.assistant"))


class RetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_category_returns_all_not_top_k(self):
        menu = Menu([item(str(i), f"Crepe {i}", "menu", "crepe") for i in range(15)])
        service = RetrievalService(menu, settings())
        context = await service.search("какие блины?")
        self.assertEqual(context.count("[MENU ITEM]"), 15)

    async def test_vegan_never_matches_vegetarian(self):
        menu = Menu(
            [item("1", "Cheese crepe", "vegetarian", "crepe"), item("2", "Plant breakfast", "vegan", "breakfast")]
        )
        service = RetrievalService(menu, settings())
        self.assertNotIn("Cheese", await service.search("vegan food"))
        self.assertIn("NO_CONTEXT", await service.search("vegan crepes"))
        self.assertNotIn("Plant", await service.search("vegetarian crepes"))

    async def test_faq_and_offline_lexical(self):
        menu = Menu(
            [
                item("1", "Panagsama Road", "info", "address"),
                item("2", "Mushroom dish 250 PHP", "menu"),
                item("3", "Open 8 AM", "info", "time"),
            ]
        )
        service = RetrievalService(menu, settings())
        self.assertIn("Panagsama", await service.search("your address"))
        self.assertNotIn("Open", await service.search("your address"))
        self.assertIn("Mushroom", await service.search("Mushroom"))
        self.assertIn("NO_CONTEXT", await service.search("unobtainium"))

    async def test_history_resolves_followup(self):
        service = RetrievalService(Menu([item("1", "Mushroom 250 PHP")]), settings())
        result = await service.search("How much is it?", [{"role": "user", "content": "Mushroom"}])
        self.assertIn("250", result)

    async def test_context_is_bounded_and_marked(self):
        service = RetrievalService(Menu([item("1", "x" * 20000, "pasta")]), settings())
        context = await service.search("pasta")
        self.assertLessEqual(len(context), MAX_CONTEXT)
        self.assertIn("TRUNCATED", context)

    async def test_unavailable_ml_degrades_and_closes(self):
        service = RetrievalService(Menu([item("1", "Mushroom")]), settings())
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            await service.start()
            await service._startup_task
        self.assertEqual(service.status, "degraded")
        self.assertIn("Mushroom", await service.search("Mushroom"))
        await service.close()
        self.assertEqual(service.status, "closed")

    async def test_start_returns_while_worker_is_loading(self):
        service = RetrievalService(Menu([]), settings())
        entered, release = threading.Event(), threading.Event()

        def initialize():
            entered.set()
            release.wait(timeout=2)

        with patch.object(service, "_initialize", initialize):
            await asyncio.wait_for(service.start(), timeout=0.2)
            await asyncio.to_thread(entered.wait, 1)
            self.assertFalse(service._startup_task.done())
            release.set()
            await service.close()

    async def test_content_change_same_count_updates_and_ids_are_stable(self):
        menu = Menu([item("one", "Mushroom 200 PHP")])
        service = semantic_service(menu)
        await service.search("Mushroom")
        first_ids = set(service._client.points)
        self.assertEqual(service._client.upserts, 1)
        await service.search("Mushroom")
        self.assertEqual(service._client.upserts, 1)
        menu.items[0]["text"] = "Mushroom 300 PHP"
        self.assertIn("300", await service.search("Mushroom"))
        self.assertEqual(service._client.upserts, 2)
        self.assertEqual(first_ids, set(service._client.points))
        self.assertEqual(service._client.deleted, [])

    async def test_persisted_hash_skips_reembedding_after_restart(self):
        menu = Menu([item("one", "Mushroom")])
        first = semantic_service(menu)
        await first.search("Mushroom")
        second = semantic_service(menu)
        second._client = first._client
        await second.search("Mushroom")
        self.assertEqual(second._client.upserts, 1)
        self.assertEqual(second._model.calls, 1)  # Only the query, not the menu.
        point = next(iter(second._client.points.values()))
        point.payload["_menu_hash"] = "partial-version"
        second._fingerprint = None
        await second.search("Mushroom")
        self.assertEqual(second._client.upserts, 2)

    async def test_stale_points_deleted_without_collection_recreation(self):
        menu = Menu([item("one", "Mushroom"), item("two", "Cheese")])
        service = semantic_service(menu)
        await service.search("Mushroom")
        stale_id = service._point_id(menu.items[1])
        menu.items.pop()
        await service.search("Mushroom")
        self.assertEqual(service._client.deleted, [stale_id])
        self.assertEqual(len(service._client.points), 1)

    async def test_dimension_mismatch_is_non_destructive(self):
        service = semantic_service(Menu([item("one", "Mushroom")]))
        service._client.exists = True
        service._client.size = 100
        self.assertIn("Mushroom", await service.search("Mushroom"))
        self.assertEqual(service.status, "degraded")
        self.assertEqual(service._client.upserts, 0)
        self.assertEqual(service._client.deleted, [])

    async def test_concurrent_model_access_is_serialized(self):
        service = semantic_service(Menu([item("one", "Mushroom")]))
        await asyncio.gather(*(service.search("Mushroom") for _ in range(8)))
        self.assertEqual(service._model.max_active, 1)
        self.assertEqual(service._client.upserts, 1)


class History:
    def __init__(self):
        self.messages = [{"role": "user", "content": "Mushroom"}]

    async def get(self, user_id):
        return list(self.messages)

    async def append(self, user_id, role, content):
        self.messages.append({"role": role, "content": content})


class AssistantTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_turns_history_and_markdown_preservation(self):
        history = History()
        seen = {}

        class Retrieval:
            async def search(self, text, history=None):
                seen["history"] = history
                return "Mushroom 250 PHP"

        async def create(**kwargs):
            seen.update(kwargs)
            self.assertEqual(len(history.messages), 1)  # Not saved before generation.
            return Record(choices=[Record(message=Record(content="**Mushroom** #1 250 PHP"))])

        service = AssistantService(settings(), Retrieval(), history)
        service._client = Record(chat=Record(completions=Record(create=create)))
        reply = await service.answer("guest", "How much is it?")
        self.assertEqual(reply, "**Mushroom** #1 250 PHP")
        self.assertEqual(seen["history"][0]["content"], "Mushroom")
        self.assertEqual([m["role"] for m in history.messages[-2:]], ["user", "assistant"])
        self.assertIn("NOT evidence", seen["messages"][0]["content"])

    async def test_failure_is_localized_and_saved_as_complete_turn(self):
        class Retrieval:
            async def search(self, *args, **kwargs):
                raise RuntimeError("offline")

        history = History()
        service = AssistantService(settings(), Retrieval(), history)
        reply = await service.answer(1, "Что есть?")
        self.assertIn("Извините", reply)
        self.assertIn("@manager", reply)
        self.assertEqual(history.messages[-1]["content"], reply)
        self.assertIn("Sorry", await service.answer(1, "Hello"))


if __name__ == "__main__":
    unittest.main()


def test_render_uses_current_metadata_price_not_stale_description():
    from pastabar.retrieval import _render

    context = _render(
        [
            {
                "id": "pasta",
                "text": "Dish: Pasta. Price: 300 PHP. / Цена: 300 PHP.",
                "metadata": {"categories": ["menu"], "price": 450},
            }
        ]
    )
    assert "300" not in context
    assert "Current price: 450 PHP" in context
