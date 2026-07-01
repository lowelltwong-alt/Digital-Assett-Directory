# Underused Python advantage map

This is not a GitHub-wide frequency claim. It is a practical list of features that many average repos and AI-generated snippets under-apply, despite being valuable for boundaries, verification, and maintainability.

## Highest priority to teach agents

| Pattern | Teach the agent to use it when | Avoid when |
|---|---|---|
| `__all__` + `_private` helpers | Module has a real public API | Tiny script |
| `@dataclass(frozen=True, slots=True, kw_only=True)` | Domain value/result/config objects | ORM/dynamic mutable object |
| `NewType` / small ID wrappers | IDs cross boundaries | Values are truly interchangeable |
| `Protocol` | Side-effect dependency boundaries | Simple local concrete code |
| `TypedDict` | Raw JSON/API/config dict shape | Internal domain logic |
| `StrEnum` / `Enum` / `Literal` | Closed states/modes | Open-ended user labels |
| `match` + `assert_never` | Closed variants/tagged unions | Simple conditionals |
| `contextlib.ExitStack` | Dynamic resource cleanup | One resource |
| `pathlib.Path` | Filesystem paths | API requires string |
| `raise ... from exc` | Wrapping lower-level errors | Sensitive error details must be hidden |
| `secrets` | Tokens/passwords/nonces | Simulation/random sampling |
| `importlib.resources` | Package templates/data | User-supplied external files |
| `tomllib` + typed Config | TOML config ingestion | Need TOML writing |
| `contextvars` | Async/request-local context | Simple synchronous code |
| `functools.singledispatch` | Type-based conversion/adapters | Core business rules |

## Strong combinations

### 1. Boundary package

```python
# package/__init__.py
from .service import SubscriptionBilling
from .types import BillingResult, CustomerId

__all__ = ["SubscriptionBilling", "BillingResult", "CustomerId"]
```

### 2. Typed value object

```python
from dataclasses import dataclass
from typing import NewType

CustomerId = NewType("CustomerId", str)

@dataclass(frozen=True, slots=True, kw_only=True)
class BillingResult:
    customer_id: CustomerId
    invoice_id: str
    amount_cents: int
```

### 3. Side-effect boundary

```python
from typing import Protocol
from pathlib import Path

class FileStore(Protocol):
    def read_text(self, path: Path) -> str: ...

class ImportCustomers:
    def __init__(self, store: FileStore) -> None:
        self._store = store
```

### 4. Closed state handling

```python
from enum import StrEnum, auto
from typing import assert_never

class Lane(StrEnum):
    GREEN = auto()
    YELLOW = auto()
    RED = auto()

def escalation_required(lane: Lane) -> bool:
    match lane:
        case Lane.GREEN:
            return False
        case Lane.YELLOW | Lane.RED:
            return True
        case other:
            assert_never(other)
```

### 5. Dynamic cleanup

```python
from contextlib import ExitStack
from pathlib import Path

def read_many(paths: list[Path]) -> list[str]:
    with ExitStack() as stack:
        files = [stack.enter_context(path.open(encoding="utf-8")) for path in paths]
        return [file.read() for file in files]
```

## Anti-patterns to suppress in AI-generated Python

- Big function with parsing, business rules, I/O, logging, subprocess, and formatting all mixed together.
- Loose dictionaries crossing every layer.
- Magic strings for closed states.
- String paths everywhere.
- `random` for tokens.
- `except Exception: pass`.
- `raise NewError(...)` without preserving `from exc`.
- `os.path` path stitching in new code where `pathlib` is clearer.
- Global mutable state for request/session data.
- Ad hoc cleanup lists instead of context managers.
- Internal helper imports from sibling modules.
- `eval`/`exec` for config, expressions, or user input.
