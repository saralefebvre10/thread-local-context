import threading
import unittest

from thread_local_context import ContextPropagator


class ContextPropagatorTests(unittest.TestCase):
    def test_set_and_get_on_same_thread(self):
        ctx = ContextPropagator()
        ctx.set("request_id", "abc-123")
        self.assertEqual(ctx.get("request_id"), "abc-123")

    def test_get_missing_key_returns_default(self):
        ctx = ContextPropagator()
        self.assertIsNone(ctx.get("nope"))
        self.assertEqual(ctx.get("nope", "fallback"), "fallback")

    def test_get_missing_key_before_any_set(self):
        ctx = ContextPropagator()
        self.assertIsNone(ctx.get("anything"))

    def test_values_do_not_leak_across_threads(self):
        ctx = ContextPropagator()
        ctx.set("trace_id", "parent")

        seen = {}
        def worker():
            seen["value"] = ctx.get("trace_id")
        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertIsNone(seen["value"])
        self.assertEqual(ctx.get("trace_id"), "parent")

    def test_snapshot_is_a_copy_and_does_not_track_live_changes(self):
        ctx = ContextPropagator()
        ctx.set("a", 1)
        snap = ctx.snapshot()
        self.assertEqual(snap, {"a": 1})

        ctx.set("b", 2)
        self.assertEqual(snap, {"a": 1})

    def test_restore_propagates_values_to_child_thread(self):
        ctx = ContextPropagator()
        ctx.set("request_id", "parent-req")
        ctx.set("user_id", 42)
        snap = ctx.snapshot()

        seen = {}
        def worker():
            ctx.restore(snap)
            seen["request_id"] = ctx.get("request_id")
            seen["user_id"] = ctx.get("user_id")
        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(seen["request_id"], "parent-req")
        self.assertEqual(seen["user_id"], 42)

    def test_restore_on_thread_does_not_affect_parent(self):
        ctx = ContextPropagator()
        ctx.set("k", "parent")
        snap = ctx.snapshot()

        def worker():
            ctx.restore(snap)
            ctx.set("k", "child")
        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(ctx.get("k"), "parent")

    def test_restore_with_empty_snapshot_clears_thread_scope(self):
        ctx = ContextPropagator()
        ctx.set("k", "v")
        self.assertEqual(ctx.snapshot(), {"k": "v"})

        ctx.restore({})
        self.assertEqual(ctx.snapshot(), {})
        self.assertIsNone(ctx.get("k"))

    def test_two_threads_restoring_same_snapshot_are_independent(self):
        ctx = ContextPropagator()
        ctx.set("shared", "base")
        snap = ctx.snapshot()

        results = {}
        barrier = threading.Barrier(2)

        def make_worker(name):
            def worker():
                ctx.restore(snap)
                barrier.wait()
                ctx.set("mutated", name)
                results[name] = ctx.snapshot()
            return worker

        t1 = threading.Thread(target=make_worker("t1"))
        t2 = threading.Thread(target=make_worker("t2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(results["t1"], {"shared": "base", "mutated": "t1"})
        self.assertEqual(results["t2"], {"shared": "base", "mutated": "t2"})

    def test_clear_empties_current_thread_scope(self):
        ctx = ContextPropagator()
        ctx.set("a", 1)
        ctx.set("b", 2)
        ctx.clear()
        self.assertEqual(ctx.snapshot(), {})
        self.assertIsNone(ctx.get("a"))

    def test_clear_only_affects_current_thread(self):
        ctx = ContextPropagator()
        ctx.set("k", "v")

        def worker():
            ctx.clear()
        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(ctx.get("k"), "v")

    def test_clear_on_thread_does_not_break_subsequent_sets(self):
        ctx = ContextPropagator()
        ctx.clear()
        ctx.set("x", 1)
        self.assertEqual(ctx.get("x"), 1)

    def test_overwrite_existing_key(self):
        ctx = ContextPropagator()
        ctx.set("k", "first")
        ctx.set("k", "second")
        self.assertEqual(ctx.get("k"), "second")

    def test_independent_propagators_share_storage_only_by_thread(self):
        ctx1 = ContextPropagator()
        ctx2 = ContextPropagator()
        ctx1.set("k", "from-1")
        ctx2.set("k", "from-2")
        self.assertEqual(ctx1.get("k"), "from-1")
        self.assertEqual(ctx2.get("k"), "from-2")


if __name__ == "__main__":
    unittest.main()
