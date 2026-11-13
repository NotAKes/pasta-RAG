"""Stable menu identity, complete validation, and content-based change detection."""

import copy
import json

import pytest

from pastabar.menu import MenuRepository


@pytest.fixture
def raw_menu():
    return [
        {"text": "Pasta 250 PHP", "metadata": {"dish_name": "Pasta", "price": 250, "categories": ["menu", "pasta"]}},
        {"text": "Salad 100 PHP", "metadata": {"dish_name": "Salad", "price": 100, "categories": ["menu", "vegan"]}},
        {"text": "Open at 8 AM", "metadata": {"categories": ["info", "hours"]}},
    ]


@pytest.fixture
def menu(tmp_path, raw_menu):
    path = tmp_path / "menu.json"
    path.write_text(json.dumps(raw_menu), encoding="utf-8")
    return MenuRepository(path)


def test_save_counts_info_but_public_menu_excludes_it(menu, raw_menu):
    assert menu.save(raw_menu) == 3
    assert len(menu.all_items()) == 3
    public = menu.public_items()
    assert len(public) == 2
    assert all("menu" in item["metadata"]["categories"] for item in public)
    assert raw_menu[0].get("id") is None  # Normalization must not mutate caller data.


def test_migration_persists_ids_and_is_idempotent(menu):
    menu.migrate_ids()
    first = menu.path.read_bytes()
    items = json.loads(first)
    assert len({item["id"] for item in items}) == 3
    assert all(isinstance(item["id"], str) and item["id"] for item in items)
    menu.migrate_ids()
    assert menu.path.read_bytes() == first


def test_saved_ids_survive_rename_reorder_and_reload(menu, raw_menu):
    menu.save(raw_menu)
    saved = menu.all_items()
    ids = [item["id"] for item in saved]
    saved[0]["metadata"]["dish_name"] = "Completely renamed pasta"
    saved[0]["text"] = "New description"
    saved[2]["text"] = "Open at 9 AM"
    saved.reverse()
    menu.save(saved)
    reloaded = MenuRepository(menu.path).all_items()
    assert [item["id"] for item in reloaded] == list(reversed(ids))
    assert reloaded[-1]["metadata"]["dish_name"] == "Completely renamed pasta"


@pytest.mark.parametrize("change", ["text", "price", "category", "info"])
def test_fingerprint_tracks_content_not_only_entry_count(menu, raw_menu, change):
    menu.save(raw_menu)
    before = menu.fingerprint()
    assert before == MenuRepository(menu.path).fingerprint()
    items = menu.all_items()
    if change == "text":
        items[0]["text"] = "Updated text"
    elif change == "price":
        items[0]["metadata"]["price"] = 251
    elif change == "category":
        items[0]["metadata"]["categories"].append("vegetarian")
    else:
        items[2]["text"] = "Open at 9 AM"
    menu.save(items)
    assert len(menu.all_items()) == 3
    assert menu.fingerprint() != before
    stable = menu.fingerprint()
    menu.save(items)
    assert menu.fingerprint() == stable


@pytest.mark.parametrize("price", [-1, "NaN", "Infinity", "not a price", 1000001, "1.001", None, True])
def test_invalid_price_cannot_replace_existing_menu(menu, raw_menu, price):
    menu.save(raw_menu)
    original = menu.path.read_bytes()
    changed = copy.deepcopy(raw_menu)
    changed[0]["metadata"]["price"] = price
    with pytest.raises(ValueError):
        menu.save(changed)
    assert menu.path.read_bytes() == original


@pytest.mark.parametrize("invalid", [[], {}, [None], [{"text": "Missing metadata"}]])
def test_invalid_menu_structure_is_rejected(invalid):
    with pytest.raises(ValueError):
        MenuRepository.normalize(invalid)


def test_duplicate_ids_are_rejected(menu, raw_menu):
    raw_menu[0]["id"] = raw_menu[1]["id"] = "same-id"
    with pytest.raises(ValueError, match="Duplicate"):
        menu.save(raw_menu)


def test_explicit_ids_are_preserved(menu, raw_menu):
    raw_menu[0]["id"] = "existing-dish-id"
    menu.save(raw_menu)
    assert menu.all_items()[0]["id"] == "existing-dish-id"


def test_repository_seed_is_valid_and_duplicate_legacy_names_have_unique_ids():
    from pathlib import Path

    seed = Path(__file__).resolve().parents[1] / "instruction.json"
    items = MenuRepository(seed).all_items()
    assert len(items) == 87
    assert len({item["id"] for item in items}) == len(items)
    assert len(MenuRepository(seed).public_items()) == 82
