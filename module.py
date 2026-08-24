from dataclasses import dataclass
from pathlib import Path
from typing import Any
import heapq
import uuid
import json
import os
import tempfile

_UNSET = object()

@dataclass
class QueueItem:
    id: str
    priority: int | float
    value: Any
    sequence: int
    version: int = 0


class PriorityQueueError(Exception):
    """Base exception for priority queue errors."""


class EmptyQueueError(PriorityQueueError):
    """Raised when an operation requires an item but the queue is empty."""


class ItemNotFoundError(PriorityQueueError):
    """Raised when the requested item ID does not exist."""


class PersistenceError(PriorityQueueError):
    """Raised when persisted queue data is invalid or cannot be accessed."""

class PersistentPriorityQueue:
    def __init__(self, file_path: str | Path = "data/queue.json"):
        self._path = Path(file_path)

        # Source of truth for active items.
        self._items: dict[str, QueueItem] = {}

        # In-memory indexes.
        self._min_heap: list[tuple] = []
        self._max_heap: list[tuple] = []

        # Used to preserve FIFO ordering for equal priorities.
        self._next_sequence = 0
        self._load()


    @staticmethod
    def _validate_priority(priority: int | float) -> None:
        if isinstance(priority, bool) or not isinstance(priority, (int, float)):
            raise ValueError("priority must be an int or float")

        if isinstance(priority, float):
            if priority != priority or priority in (float("inf"), float("-inf")):
                raise ValueError("priority must be finite")


    @staticmethod
    def _min_entry(item: QueueItem) -> tuple:
        return (
            item.priority,
            item.sequence,
            item.version,
            item.id,
        )

    @staticmethod
    def _max_entry(item: QueueItem) -> tuple:
        return (
            -item.priority,
            item.sequence,
            item.version,
            item.id,
        )
    def insert(self, priority: int | float, value: Any) -> QueueItem:
        self._validate_priority(priority)

        item = QueueItem(
            id=str(uuid.uuid4()),
            priority=priority,
            value=value,
            sequence=self._next_sequence,
        )

        new_items = self._items.copy()
        new_items[item.id] = item

        new_next_sequence = self._next_sequence + 1

        # Persist candidate state first.
        self._save_state(new_items, new_next_sequence)

        # Commit to memory only after persistence succeeds.
        self._items = new_items
        self._next_sequence = new_next_sequence

        heapq.heappush(self._min_heap, self._min_entry(item))
        heapq.heappush(self._max_heap, self._max_entry(item))

        return item

    def _is_entry_valid(self, entry: tuple) -> bool:
        _, _, version, item_id = entry

        item = self._items.get(item_id)

        if item is None:
            return False

        return item.version == version
    
    def peek(self, mode: str = "min") -> QueueItem:
        if mode not in ("min", "max"):
            raise ValueError("mode must be 'min' or 'max'")

        heap = self._min_heap if mode == "min" else self._max_heap

        while heap:
            entry = heap[0]

            if self._is_entry_valid(entry):
                return self._items[entry[3]]

            heapq.heappop(heap)

        raise EmptyQueueError("priority queue is empty")


    def extract_min(self) -> QueueItem:
        while self._min_heap:
            entry = self._min_heap[0]

            if not self._is_entry_valid(entry):
                heapq.heappop(self._min_heap)
                continue

            _, _, _, item_id = entry
            item = self._items[item_id]

            new_items = self._items.copy()
            del new_items[item_id]

            # Persist before modifying the heap.
            self._save_state(new_items, self._next_sequence)

            # Commit after persistence succeeds.
            heapq.heappop(self._min_heap)
            self._items = new_items

            return item

        raise EmptyQueueError("priority queue is empty")
    
    def _item_to_dict(self, item: QueueItem) -> dict:
        return {
            "id": item.id,
            "priority": item.priority,
            "value": item.value,
            "sequence": item.sequence,
            "version": item.version,
        }

    def _state_to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "next_sequence": self._next_sequence,
            "items": [
                self._item_to_dict(item)
                for item in self._items.values()
            ],
        }

    def _save(self) -> None:
        self._save_state(self._items, self._next_sequence)

    def _load(self) -> None:
        if not self._path.exists():
            return

        try:
            with self._path.open("r", encoding="utf-8") as file:
                state = json.load(file)

            if not isinstance(state, dict):
                raise PersistenceError("Queue file must contain a JSON object")

            if state.get("schema_version") != 1:
                raise PersistenceError("Unsupported queue schema version")

            items_data = state.get("items")
            next_sequence = state.get("next_sequence")

            if not isinstance(items_data, list):
                raise PersistenceError("'items' must be a list")

            if not isinstance(next_sequence, int) or next_sequence < 0:
                raise PersistenceError(
                    "'next_sequence' must be a non-negative integer"
                )

            for data in items_data:
                if not isinstance(data, dict):
                    raise PersistenceError("Each item must be a JSON object")

                required_fields = {
                    "id",
                    "priority",
                    "value",
                    "sequence",
                    "version",
                }

                if not required_fields.issubset(data):
                    raise PersistenceError("Invalid queue item")

                item = QueueItem(
                    id=data["id"],
                    priority=data["priority"],
                    value=data["value"],
                    sequence=data["sequence"],
                    version=data["version"],
                )

                self._validate_priority(item.priority)

                self._items[item.id] = item

                self._min_heap.append(
                    (
                        item.priority,
                        item.sequence,
                        item.version,
                        item.id,
                    )
                )

                self._max_heap.append(
                    (
                        -item.priority,
                        item.sequence,
                        item.version,
                        item.id,
                    )
                )

            self._next_sequence = next_sequence

            heapq.heapify(self._min_heap)
            heapq.heapify(self._max_heap)

        except json.JSONDecodeError as exc:
            raise PersistenceError(
                f"Invalid JSON in {self._path}"
            ) from exc
        except OSError as exc:
            raise PersistenceError(
                f"Failed to read queue from {self._path}"
            ) from exc


    def extract_max(self) -> QueueItem:
        while self._max_heap:
            entry = self._max_heap[0]

            if not self._is_entry_valid(entry):
                heapq.heappop(self._max_heap)
                continue

            _, _, _, item_id = entry
            item = self._items[item_id]

            new_items = self._items.copy()
            del new_items[item_id]

            # Persist before modifying the heap.
            self._save_state(new_items, self._next_sequence)

            # Commit after persistence succeeds.
            heapq.heappop(self._max_heap)
            self._items = new_items

            return item

        raise EmptyQueueError("priority queue is empty")

    def is_empty(self) -> bool:
        return not self._items

    def update(
    self,
    item_id: str,
    priority: int | float | None = None,
    value: Any = _UNSET,
) -> QueueItem:
        if priority is None and value is _UNSET:
            raise ValueError("provide priority or value to update")

        item = self._items.get(item_id)

        if item is None:
            raise ItemNotFoundError(f"item not found: {item_id}")

        if priority is not None:
            self._validate_priority(priority)

        new_item = QueueItem(
            id=item.id,
            priority=item.priority if priority is None else priority,
            value=item.value if value is _UNSET else value,
            sequence=item.sequence,
            version=item.version + 1,
        )

        new_items = self._items.copy()
        new_items[item_id] = new_item

        # Persist first.
        self._save_state(new_items, self._next_sequence)

        # Commit only after persistence succeeds.
        self._items = new_items

        heapq.heappush(
            self._min_heap,
            self._min_entry(new_item),
        )

        heapq.heappush(
            self._max_heap,
            self._max_entry(new_item),
        )

        return new_item
    
    def delete(self, item_id: str) -> QueueItem:
        item = self._items.get(item_id)

        if item is None:
            raise ItemNotFoundError(f"item not found: {item_id}")

        new_items = self._items.copy()
        del new_items[item_id]

        # Persist first.
        self._save_state(new_items, self._next_sequence)

        # Commit only after persistence succeeds.
        self._items = new_items

        return item
    
    def _save_state(self, items: dict[str, QueueItem], next_sequence: int) -> None:
        state = {
            "schema_version": 1,
            "next_sequence": next_sequence,
            "items": [
                self._item_to_dict(item)
                for item in items.values()
            ],
        }

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
            ) as temp_file:
                json.dump(state, temp_file, indent=2)
                temp_path = Path(temp_file.name)

            os.replace(temp_path, self._path)

        except (OSError, TypeError, ValueError) as exc:
            if "temp_path" in locals():
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

            raise PersistenceError(
                f"Failed to save queue to {self._path}"
            ) from exc