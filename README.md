# Persistent Priority Queue

A file-backed priority queue implemented in Python using two heaps and JSON persistence.

## Features

* Insert items with a priority
* Peek minimum-priority item
* Peek maximum-priority item
* Extract minimum-priority item
* Extract maximum-priority item
* Update item priority or value
* Delete items by ID
* FIFO ordering for equal priorities
* Persistent JSON storage
* Version-based stale heap entry detection
* Atomic file replacement during persistence
* Custom exceptions
* Automated pytest test suite

## Real-World Use Cases

Priority queues are useful whenever work needs to be processed according to importance or urgency rather than simple arrival order.

Examples include:

- **Task scheduling:** Execute high-priority jobs before lower-priority jobs.
- **Operating systems:** Schedule processes based on priority.
- **Network systems:** Process latency-sensitive or high-priority packets first.
- **Pathfinding:** Algorithms such as Dijkstra's and A* use priority queues to select the next most promising node.
- **Event-driven systems:** Process events according to their scheduled time or priority.
- **Background job processing:** Process urgent jobs before normal or low-priority jobs.
- 
## Design

The queue uses:

* `_items` as the source of truth
* A min-heap for minimum-priority operations
* A max-heap for maximum-priority operations
* A monotonically increasing sequence number for FIFO tie-breaking
* A version number for invalidating stale heap entries

Heap entries have the form:

```text
(priority, sequence, version, id)
```

The max-heap stores the negative priority:

```text
(-priority, sequence, version, id)
```

Updates use lazy deletion. Instead of searching through both heaps, an updated item receives a new version. Older heap entries become stale and are discarded when encountered.

## Persistence

Queue state is stored as JSON.

The persisted format contains:

```json
{
  "schema_version": 1,
  "next_sequence": 0,
  "items": []
}
```

Writes use a temporary file followed by `os.replace()` so the target file is replaced atomically.

## Installation

Python 3.10+ is recommended.

Install pytest:

```powershell
python -m pip install pytest
```

## Running Tests

Run the complete test suite with:

```powershell
python -m pytest -q
```

## Example

```python
from module import PersistentPriorityQueue

queue = PersistentPriorityQueue("data/queue.json")

queue.insert(5, "Task A")
queue.insert(2, "Task B")
queue.insert(8, "Task C")

print(queue.peek("min"))
print(queue.peek("max"))

print(queue.extract_min())
print(queue.extract_max())
```

## Testing

The project includes tests covering:

* Basic queue operations
* Min/max behavior
* FIFO tie-breaking
* Updates
* Deletes
* Stale heap entries
* Persistence across process restarts
* Corrupted JSON
* Invalid schemas
* Invalid priorities
* JSON serialization failures
* Multiple updates
* Persistence after mutation

## Project Structure

```text
persistent-priority-queue/
├── module.py
├── test_module.py
├── README.md
├── .gitignore
└── data/
    └── queue.json
```

`data/`, `__pycache__/`, and `.pytest_cache/` are runtime/generated files and should not be committed.

## Run Tests Again

```powershell
python -m pytest -q
```
