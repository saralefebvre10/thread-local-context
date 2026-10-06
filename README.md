# Thread Local Context

A small carrier object that propagates request-scoped values across threads using `threading.local` with explicit `snapshot` and `restore` for child tasks.

```python
from thread_local_context import ContextPropagator

ctx = ContextPropagator()
ctx.set("request_id", "abc-123")

snap = ctx.snapshot()  # capture on the current thread

# ...in a worker thread...
ctx.restore(snap)       # re-establish the same bindings there
ctx.get("request_id")   # -> "abc-123"
```

## Why this exists

When a request handler hands work to a thread pool, per-request values like correlation ids and trace ids do not follow the new thread automatically. `threading.local` gives you isolation but not propagation; `contextvars` gives you both but is geared toward async, and its behaviour under manual `Thread` targets is subtle. This library picks the simpler, more predictable model: values are thread-isolated by default, and the caller is responsible for explicitly copying them across the boundary via `snapshot()` / `restore()`. There is no automatic inheritance, so nothing happens behind your back.

Exported names: `ContextPropagator`, with methods `set(key, value)`, `get(key, default=None)`, `snapshot()`, `restore(snapshot)`, and `clear()`.

## The awkward edge

`restore()` replaces the current thread's entire scope with a copy of the snapshot. If you set a key on the child thread *before* calling `restore()`, that value is discarded. The intended usage is to restore first, then mutate. Likewise, `clear()` only affects the calling thread — a parent thread's bindings survive a child calling `clear()`.

Run the tests with `PYTHONPATH=src python -m unittest discover -s tests`.
