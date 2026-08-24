import json
from module import PersistenceError

import pytest

from module import (
    EmptyQueueError,
    ItemNotFoundError,
    PersistentPriorityQueue,
)

@pytest.fixture
def queue(tmp_path):
    return PersistentPriorityQueue(tmp_path / "queue.json")

def test_new_queue_is_empty(queue):
    assert queue.is_empty()

def test_insert(queue):
    item = queue.insert(5, "Task A")

    assert item.priority == 5
    assert item.value == "Task A"
    assert item.sequence == 0
    assert item.version == 0
    assert item.id in queue._items
    assert not queue.is_empty()

def test_peek_min_and_max(queue):
    queue.insert(5, "A")
    queue.insert(2, "B")
    queue.insert(8, "C")

    assert queue.peek("min").value == "B"
    assert queue.peek("max").value == "C"

    assert len(queue._items) == 3

def test_extract_min(queue):
    queue.insert(5, "A")
    queue.insert(2, "B")
    queue.insert(8, "C")

    item = queue.extract_min()

    assert item.value == "B"
    assert item.priority == 2
    assert len(queue._items) == 2

def test_extract_max(queue):
    queue.insert(5, "A")
    queue.insert(2, "B")
    queue.insert(8, "C")

    item = queue.extract_max()

    assert item.value == "C"
    assert item.priority == 8
    assert len(queue._items) == 2

def test_equal_priority_is_fifo(queue):
    first = queue.insert(5, "First")
    second = queue.insert(5, "Second")
    third = queue.insert(5, "Third")

    assert queue.extract_min().id == first.id
    assert queue.extract_min().id == second.id
    assert queue.extract_min().id == third.id

def test_equal_priority_max_is_fifo(queue):
    first = queue.insert(5, "First")
    second = queue.insert(5, "Second")
    third = queue.insert(5, "Third")

    assert queue.extract_max().id == first.id
    assert queue.extract_max().id == second.id
    assert queue.extract_max().id == third.id

def test_update_priority(queue):
    item = queue.insert(10, "Task")

    updated = queue.update(item.id, priority=1)

    assert updated.priority == 1
    assert updated.version == 1
    assert queue.peek("min").id == item.id

def test_update_value(queue):
    item = queue.insert(5, "Old")

    updated = queue.update(item.id, value="New")

    assert updated.value == "New"
    assert updated.priority == 5
    assert updated.version == 1

def test_update_value_to_none(queue):
    item = queue.insert(5, "Old")

    updated = queue.update(item.id, value=None)

    assert updated.value is None

def test_delete(queue):
    item = queue.insert(5, "Task")

    deleted = queue.delete(item.id)

    assert deleted.id == item.id
    assert item.id not in queue._items
    assert queue.is_empty()

def test_update_missing_item(queue):
    with pytest.raises(ItemNotFoundError):
        queue.update("does-not-exist", priority=5)

def test_delete_missing_item(queue):
    with pytest.raises(ItemNotFoundError):
        queue.delete("does-not-exist")

def test_extract_min_empty(queue):
    with pytest.raises(EmptyQueueError):
        queue.extract_min()


def test_extract_max_empty(queue):
    with pytest.raises(EmptyQueueError):
        queue.extract_max()

def test_invalid_peek_mode(queue):
    with pytest.raises(ValueError):
        queue.peek("middle")

def test_persistence_across_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)

    first = queue1.insert(5, "First")
    second = queue1.insert(2, "Second")
    third = queue1.insert(8, "Third")

    queue2 = PersistentPriorityQueue(path)

    assert len(queue2._items) == 3
    assert queue2.peek("min").id == second.id
    assert queue2.peek("max").id == third.id

def test_extraction_persists_across_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)

    first = queue1.insert(5, "First")
    second = queue1.insert(10, "Second")

    removed = queue1.extract_min()

    assert removed.id == first.id

    queue2 = PersistentPriorityQueue(path)

    assert first.id not in queue2._items
    assert second.id in queue2._items

def test_corrupted_json_raises_persistence_error(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(PersistenceError):
        PersistentPriorityQueue(path)

def test_invalid_schema_raises_persistence_error(tmp_path):
    path = tmp_path / "queue.json"

    path.write_text(
        json.dumps({
            "schema_version": 999,
            "next_sequence": 0,
            "items": [],
        }),
        encoding="utf-8",
    )

    with pytest.raises(PersistenceError):
        PersistentPriorityQueue(path)

def test_invalid_item_raises_persistence_error(tmp_path):
    path = tmp_path / "queue.json"

    path.write_text(
        json.dumps({
            "schema_version": 1,
            "next_sequence": 1,
            "items": [
                {
                    "id": "abc",
                    "priority": 5
                }
            ],
        }),
        encoding="utf-8",
    )

    with pytest.raises(PersistenceError):
        PersistentPriorityQueue(path)

def test_equal_priority_fifo_survives_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)

    first = queue1.insert(5, "First")
    second = queue1.insert(5, "Second")
    third = queue1.insert(5, "Third")

    queue2 = PersistentPriorityQueue(path)

    assert queue2.extract_min().id == first.id
    assert queue2.extract_min().id == second.id
    assert queue2.extract_min().id == third.id

def test_equal_priority_max_fifo_survives_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)

    first = queue1.insert(5, "First")
    second = queue1.insert(5, "Second")
    third = queue1.insert(5, "Third")

    queue2 = PersistentPriorityQueue(path)

    assert queue2.extract_max().id == first.id
    assert queue2.extract_max().id == second.id
    assert queue2.extract_max().id == third.id

def test_multiple_updates_keep_latest_version(queue):
    item = queue.insert(10, "Task")

    updated1 = queue.update(item.id, priority=5)
    updated2 = queue.update(item.id, priority=1)
    updated3 = queue.update(item.id, priority=8)

    assert updated1.version == 1
    assert updated2.version == 2
    assert updated3.version == 3

    assert queue.peek("min").priority == 8
    assert queue.peek("max").priority == 8

    assert queue.extract_min().id == item.id

def test_multiple_updates_do_not_return_stale_max(queue):
    item = queue.insert(10, "Task")
    other = queue.insert(7, "Other")

    queue.update(item.id, priority=1)

    assert queue.peek("max").id == other.id
    assert queue.extract_max().id == other.id
    assert queue.extract_max().id == item.id

def test_negative_priority_is_allowed(queue):
    item = queue.insert(-10, "Low")

    assert item.priority == -10
    assert queue.peek("min").priority == -10

def test_invalid_priority_is_rejected(queue):
    with pytest.raises(ValueError):
        queue.insert("high", "Task")

    with pytest.raises(ValueError):
        queue.insert(None, "Task")

    with pytest.raises(ValueError):
        queue.insert(True, "Task")

def test_non_finite_priority_is_rejected(queue):
    with pytest.raises(ValueError):
        queue.insert(float("nan"), "Task")

    with pytest.raises(ValueError):
        queue.insert(float("inf"), "Task")

    with pytest.raises(ValueError):
        queue.insert(float("-inf"), "Task")

def test_non_json_value_raises_persistence_error(queue):
    with pytest.raises(PersistenceError):
        queue.insert(5, {1, 2, 3})

def test_update_persists_across_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)
    item = queue1.insert(10, "Original")

    updated = queue1.update(item.id, priority=2, value="Updated")

    queue2 = PersistentPriorityQueue(path)

    loaded = queue2._items[item.id]

    assert loaded.priority == 2
    assert loaded.value == "Updated"
    assert loaded.version == 1

def test_delete_persists_across_restart(tmp_path):
    path = tmp_path / "queue.json"

    queue1 = PersistentPriorityQueue(path)
    item = queue1.insert(5, "Delete me")

    queue1.delete(item.id)

    queue2 = PersistentPriorityQueue(path)

    assert item.id not in queue2._items
    assert queue2.is_empty()