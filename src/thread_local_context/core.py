import threading
from typing import Any, Dict


class ContextPropagator:
    """A carrier object that propagates request-scoped values across threads.

    Each ``ContextPropagator`` instance owns a ``threading.local`` storage cell,
    so values set on one thread are invisible on another until explicitly copied
    via :meth:`snapshot` and :meth:`restore`. This is the building block for
    propagating correlation ids, trace ids, or per-request configuration from a
    parent thread into a worker thread or thread pool task, without relying on
    any global mutable state shared between unrelated requests.
    """

    def __init__(self) -> None:
        # ``threading.local`` isolates per-thread attribute namespaces, which is
        # exactly the semantics we want: a value set on thread A must not leak
        # onto thread B. We store a single dict rather than many attributes so
        # that snapshot/restore can be a whole-sale copy of the current scope.
        self._local = threading.local()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _scope(self) -> Dict[str, Any]:
        # Lazily materialise the per-thread dict so callers never see an
        # AttributeError when no value has been set yet on this thread.
        scope = getattr(self._local, "scope", None)
        if scope is None:
            scope = {}
            self._local.scope = scope
        return scope

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Bind ``key`` to ``value`` on the calling thread only."""
        self._scope()[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for ``key`` on the calling thread, or ``default``."""
        return self._scope().get(key, default)

    def snapshot(self) -> Dict[str, Any]:
        """Return a shallow copy of the calling thread's scope.

        The copy is independent: mutating it has no effect on the live scope.
        Pass the returned dict to :meth:`restore` on another thread to
        re-establish the same bindings there.
        """
        return dict(self._scope())

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Replace the calling thread's scope with a copy of ``snapshot``."""
        # Copy defensively so two threads restoring from the same snapshot
        # don't share one mutable dict object and step on each other.
        self._local.scope = dict(snapshot)

    def clear(self) -> None:
        """Remove every binding from the calling thread's scope."""
        self._local.scope = {}
