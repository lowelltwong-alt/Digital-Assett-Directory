# Python language surface taxonomy for AI agents

## 1. Reserved keywords

```text
False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield
```

Teach the agent: keywords are not just syntax. They mark control flow, scope, exception handling, imports, async boundaries, and function/class definitions.

## 2. Soft keywords

```text
match case _ type
```

Use these only in their context-specific roles. `_` is a wildcard in `match`; elsewhere it is just a normal name by convention.

## 3. Identifier classes

```text
_public_name
_internal_name
__class_private_name
__dunder_protocol_name__
_
```

Preferred teaching rule:

- `_internal_name`: internal implementation detail.
- `__dunder__`: only use documented dunder protocols.
- `__class_private`: use rarely; usually single underscore is better.
- `_`: unused variable or match wildcard.

## 4. Operators and single-symbol tools

Use operators to express domain intent only when the meaning is obvious.

High-value symbols:

- `:` starts suites, slices, dict entries, annotations.
- `->` declares return type.
- `@` declares decorators; expression `@` is matrix multiplication.
- `:=` assignment expression; use sparingly.
- `*` and `**` packing/unpacking; use for explicit shape adaptation.
- `|` type union, set union, dict merge; useful but easy to overload mentally.
- `...` ellipsis; placeholder or multidimensional slicing, not unfinished production code.
- `with` + context manager beats manual try/finally for resource lifetimes.
- `match` beats long `if/elif` only for structured closed variants.

## 5. Builtins

The most under-leveraged builtins in AI-generated Python are often:

- `enumerate`
- `zip`
- `all`
- `any`
- `sum`
- `sorted`
- `reversed`
- `iter`
- `next`
- `slice`
- `property`
- `classmethod`
- `staticmethod`
- `super`
- `isinstance`
- `issubclass`
- `callable`
- `getattr`
- `setattr`
- `hasattr`
- `vars`

The most dangerous builtins when used casually:

- `eval`
- `exec`
- `compile`
- `open` without clear encoding/path handling
- `globals`
- `locals`
- `__import__`

## 6. Dunder protocols

Use dunders to make an object obey a Python protocol; do not invent undocumented dunders.

High-value protocols:

- construction: `__init__`, `__post_init__`, `__new__`
- representation: `__repr__`, `__str__`
- truth/size: `__bool__`, `__len__`
- iteration: `__iter__`, `__next__`
- containment/indexing: `__contains__`, `__getitem__`
- context managers: `__enter__`, `__exit__`, `__aenter__`, `__aexit__`
- callable objects: `__call__`
- comparison/hashing: `__eq__`, `__hash__`, ordering dunders
- class customization: `__init_subclass__`, `__set_name__`, `__class_getitem__`
- pattern matching: `__match_args__`
- memory/attribute surface: `__slots__`

## 7. Standard library advantage modules

Teach the agent to check these before inventing custom infrastructure:

- `dataclasses`
- `typing`
- `enum`
- `pathlib`
- `contextlib`
- `functools`
- `collections`
- `itertools`
- `abc`
- `contextvars`
- `importlib.resources`
- `tomllib`
- `tempfile`
- `secrets`
- `logging`
- `warnings`
- `subprocess`
- `sqlite3`
- `decimal`
- `fractions`
- `zoneinfo`
- `graphlib`
