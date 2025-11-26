"""Tests for qcrawl.core.item.Item"""

import pytest

from qcrawl.core.item import Item


def test_init_empty():
    """Item initializes with empty data and metadata when no args provided."""
    item = Item()
    assert item.data == {}
    assert item.metadata == {}


def test_init_with_data_and_metadata():
    """Item initializes with provided data and metadata."""
    data = {"title": "Test", "price": 10.99}
    metadata: dict[str, object] = {"depth": 2, "timestamp": 123456}
    item = Item(data=data, metadata=metadata)
    assert item.data == data
    assert item.metadata == metadata


def test_init_with_none():
    """Item handles None for data/metadata (converts to empty dict)."""
    item = Item(data=None, metadata=None)
    assert item.data == {}
    assert item.metadata == {}


def test_getitem_and_setitem():
    """item[key] gets and sets values in data."""
    item = Item()
    item["title"] = "Test"
    assert item["title"] == "Test"


def test_getitem_missing_raises_keyerror():
    """item[missing_key] raises KeyError."""
    item = Item()
    with pytest.raises(KeyError):
        _ = item["missing"]


def test_contains():
    """'key' in item checks if key exists."""
    item = Item(data={"title": "Test"})
    assert "title" in item
    assert "missing" not in item


def test_get():
    """item.get(key, default) returns value or default."""
    item = Item(data={"title": "Test"})
    assert item.get("title") == "Test"
    assert item.get("missing") is None
    assert item.get("missing", "default") == "default"


def test_keys_values_items():
    """keys(), values(), items() return views over data."""
    item = Item(data={"a": 1, "b": 2})
    assert set(item.keys()) == {"a", "b"}
    assert set(item.values()) == {1, 2}
    assert set(item.items()) == {("a", 1), ("b", 2)}


def test_repr():
    """repr() shows Item with data and metadata."""
    item = Item(data={"title": "Test"}, metadata={"depth": 1})
    assert repr(item) == "Item(data={'title': 'Test'}, metadata={'depth': 1})"


def test_data_metadata_are_mutable():
    """Mutating data/metadata properties changes the item."""
    item = Item(data={"a": 1}, metadata={"depth": 1})
    item.data["b"] = 2
    item.metadata["timestamp"] = 999
    assert item.data == {"a": 1, "b": 2}
    assert item.metadata == {"depth": 1, "timestamp": 999}


def test_complex_data_types():
    """Item handles nested structures and various types."""
    item = Item(
        data={
            "nested": {"a": 1},
            "list": [1, 2, 3],
            "none": None,
            "bool": True,
        }
    )
    assert item["nested"] == {"a": 1}
    assert item["list"] == [1, 2, 3]
    assert item["none"] is None
    assert item["bool"] is True
