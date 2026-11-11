"""Phase 2 acceptance (GO/NO-GO): exact reproduction with zero provider calls."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from harness import HermesRun, response, tool_result


def record_three_step_run(h: HermesRun, session: str = "sess-parent") -> dict:
    """Record: llm(read_file) -> tool(read_file ENOENT) -> llm(final answer)."""
    provider: list = []
    tools: list = []
    h.llm(
        session,
        {"messages": [{"role": "user", "content": "fix the build"}]},
        response(tool_calls=[{"id": "call_1", "name": "read_file", "arguments": {"path": "config/dev.yaml"}}]),
        provider,
    )
    h.tool(
        session,
        "read_file",
        {"path": "config/dev.yaml"},
        tool_result(False, error="FileNotFoundError: config/dev.yaml"),
        "call_1",
        tools,
    )
    h.llm(
        session,
        {"messages": [{"role": "user", "content": "fix the build"}]},
        response("I could not read config/dev.yaml."),
        provider,
    )
    assert len(provider) == 2 and len(tools) == 1
    return h.state.list_runs()[0]


class TestExactReproduction(unittest.TestCase):
    def test_no_edit_replay_reproduces_every_step_with_zero_calls(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            run_id = run["run_id"]
            recorded = h.state.load_steps(h.state.read_trace(run_id))

            armed = h.call("mg_rewind", {"run_id": run_id})
            self.assertTrue(armed["ok"], armed)
            self.assertEqual(armed["branch_at"], 3)
            nonce = h.state.pending().nonce

            child = "sess-child-1"
            provider_calls: list = []
            tool_calls: list = []

            # The child's first request carries the replay nonce (bound from context).
            first = h.llm(
                child,
                {"messages": [{"role": "user", "content": f"{nonce} continue the task"}]},
                response("LIVE-RESPONSE-SHOULD-NOT-BE-USED"),
                provider_calls,
            )
            self.assertEqual(provider_calls, [], "served llm step must not reach the provider")
            self.assertIs(first, recorded and h.state.recall_object(run_id, 0),
                          "replay returns the exact recorded response object")

            served_tool = h.tool(
                child,
                "read_file",
                {"path": "config/dev.yaml"},
                tool_result(True, content="LIVE-TOOL-RESULT-SHOULD-NOT-BE-USED"),
                "call_1",
                tool_calls,
            )
            self.assertEqual(tool_calls, [], "served tool step must not execute the tool")
            self.assertEqual(served_tool, recorded[1]["result"])

            last = h.llm(child, {"messages": [{"role": "user", "content": "continue"}]},
                         response("LIVE"), provider_calls)
            self.assertEqual(provider_calls, [])
            self.assertEqual(last.choices[0].message.content, "I could not read config/dev.yaml.")

            state = h.state.get_state(child)
            summary = state.summary()
            self.assertEqual(summary["served_llm"], 2)
            self.assertEqual(summary["served_tool"], 1)
            self.assertEqual(summary["live_llm"], 0)
            self.assertEqual(summary["live_tool"], 0)
            self.assertIsNone(summary["desync"])
            self.assertIsNone(summary["error"])
            self.assertEqual(summary["cursor"], 3)

            # Exact reproduction adds no branch trace: nothing ran live.
            self.assertEqual([r["run_id"] for r in h.state.list_runs()], [run_id])

    def test_replay_from_disk_snapshot_when_the_live_object_is_gone(self):
        """The demo replays in a new process: the recorded JSON must rebuild a usable response."""
        with HermesRun() as h:
            run = record_three_step_run(h)
            run_id = run["run_id"]
            # Drop every in-memory provider object, as a process restart would.
            h.state._OBJECTS.clear()
            h.state._OBJECTS_ORDER.clear()

            h.call("mg_rewind", {"run_id": run_id})
            nonce = h.state.pending().nonce
            provider: list = []
            served = h.llm("sess-child-disk", {"messages": [{"role": "user", "content": nonce}]},
                           response("LIVE"), provider)
            self.assertEqual(provider, [])
            message = served.choices[0].message
            self.assertEqual(message.role, "assistant")
            self.assertEqual(len(message.tool_calls), 1)
            self.assertEqual(message.tool_calls[0].function.name, "read_file")
            self.assertEqual(json.loads(message.tool_calls[0].function.arguments), {"path": "config/dev.yaml"})
            self.assertEqual(served.usage.total_tokens, 15)

    def test_replay_is_side_effect_free_on_disk(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            path = h.state.run_path(run["run_id"])
            before = path.read_bytes()
            h.call("mg_rewind", {"run_id": run["run_id"]})
            nonce = h.state.pending().nonce
            h.llm("sess-child-2", {"messages": [{"role": "user", "content": nonce}]},
                  response("x"), [])
            self.assertEqual(path.read_bytes(), before, "serving must never mutate the recorded trace")

    def test_unbound_child_runs_live_and_does_not_steal_the_record(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            h.call("mg_rewind", {"run_id": run["run_id"]})
            provider: list = []
            h.llm("sess-unrelated", {"messages": [{"role": "user", "content": "unrelated session"}]},
                  response("live answer"), provider)
            self.assertEqual(len(provider), 1, "a session without the nonce must not be served")
            self.assertIsNotNone(h.state.pending(), "the armed replay stays armed")

    def test_tool_steps_are_matched_by_tool_call_id_when_out_of_order(self):
        with HermesRun() as h:
            session = "sess-parallel"
            h.llm(
                session,
                {"messages": [{"role": "user", "content": "read two files"}]},
                response(tool_calls=[
                    {"id": "call_a", "name": "read_file", "arguments": {"path": "a"}},
                    {"id": "call_b", "name": "read_file", "arguments": {"path": "b"}},
                ]),
                [],
            )
            h.tool(session, "read_file", {"path": "a"}, tool_result(True, content="A"), "call_a", [])
            h.tool(session, "read_file", {"path": "b"}, tool_result(True, content="B"), "call_b", [])
            run_id = h.state.list_runs()[0]["run_id"]

            h.call("mg_rewind", {"run_id": run_id})
            nonce = h.state.pending().nonce
            h.llm("sess-child-p", {"messages": [{"role": "user", "content": nonce}]}, response("x"), [])

            live: list = []
            # Reverse order: b then a. Ordinal serving would hand back the wrong result.
            got_b = h.tool("sess-child-p", "read_file", {"path": "b"}, "LIVE", "call_b", live)
            got_a = h.tool("sess-child-p", "read_file", {"path": "a"}, "LIVE", "call_a", live)
            self.assertEqual(live, [])
            self.assertEqual(json.loads(got_b)["content"], "B")
            self.assertEqual(json.loads(got_a)["content"], "A")

    def test_desync_fails_open_to_live_and_is_recorded(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            h.call("mg_rewind", {"run_id": run["run_id"]})
            nonce = h.state.pending().nonce
            h.llm("sess-child-d", {"messages": [{"role": "user", "content": nonce}]}, response("x"), [])

            live_tools: list = []
            # Step 1 expects read_file; this call is a different tool -> desync.
            h.tool("sess-child-d", "write_file", {"path": "x"}, tool_result(True), "call_zzz", live_tools)
            self.assertEqual(len(live_tools), 1, "desync must fail open to live execution")

            state = h.state.get_state("sess-child-d")
            self.assertIsNotNone(state.desync)
            self.assertEqual(state.desync["expected"], "write_file")
            branch_runs = [r for r in h.state.list_runs() if r.get("branch_of") == run["run_id"]]
            self.assertEqual(len(branch_runs), 1, "the live remainder is recorded as a branch")


class TestConcurrency(unittest.TestCase):
    def test_parallel_tool_calls_get_distinct_sequence_numbers(self):
        """Parallel tool calls run on a thread pool; recording must not collide on seq."""
        with HermesRun() as h:
            import threading

            session = "sess-concurrent"
            h.llm(session, {"messages": [{"role": "user", "content": "read four files"}]},
                  response(tool_calls=[{"id": f"call_{i}", "name": "read_file", "arguments": {"path": str(i)}}
                                       for i in range(4)]), [])
            threads = []
            for index in range(4):
                thread = threading.Thread(
                    target=h.tool,
                    args=(session, "read_file", {"path": str(index)},
                          tool_result(True, content=str(index)), f"call_{index}", []),
                )
                threads.append(thread)
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            steps = h.state.load_steps(h.state.read_trace(h.state.list_runs()[0]["run_id"]))
            self.assertEqual([s["seq"] for s in steps], [0, 1, 2, 3, 4])
            self.assertEqual(len({s["tool_call_id"] for s in steps[1:]}), 4)


class _FakeService:
    """Stands in for ctx.subagent_lifecycle; runs the child script inline."""

    def __init__(self, h: HermesRun, script, request_box: dict):
        self.h = h
        self.script = script
        self.request_box = request_box
        self.launched = None

    def launch(self, request):
        self.launched = request
        self.request_box["request"] = request
        nonce = "MULLIGAN-" + request.context.split("MULLIGAN-")[1].split()[0]
        self.script(self.h, "sess-child-play", nonce)
        return SimpleNamespace(subagent_id="sub-1")

    def wait(self, handle, timeout_seconds=None):
        return SimpleNamespace(timed_out=False)

    def result(self, handle):
        return SimpleNamespace(state=SimpleNamespace(value="succeeded"), summary="branch finished", error_message=None)


class TestPlayFlow(unittest.TestCase):
    def test_mg_play_launches_a_child_with_the_nonce_and_reports_serving(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            self.assertTrue(h.call("mg_rewind", {"run_id": run["run_id"]})["ok"])
            nonce = h.state.pending().nonce

            provider: list = []
            tools: list = []

            def child_script(run_harness, session, nonce_from_request):
                self.assertEqual(nonce_from_request, nonce)
                run_harness.llm(session, {"messages": [{"role": "user", "content": nonce_from_request}]},
                                response("LIVE"), provider)
                run_harness.tool(session, "read_file", {"path": "config/dev.yaml"},
                                 tool_result(True, content="LIVE"), "call_1", tools)
                run_harness.llm(session, {"messages": [{"role": "user", "content": "go"}]},
                                response("LIVE"), provider)

            box: dict = {}
            service = _FakeService(h, child_script, box)
            out = json.loads(
                h.module.mg_tools.mg_play(
                    {"run_id": run["run_id"]}, ctx=SimpleNamespace(subagent_lifecycle=service),
                    session_id="sess-parent",
                )
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(provider, [], "mg_play's child made zero provider calls")
            self.assertEqual(tools, [], "mg_play's child executed zero tools")
            self.assertIn("0 provider calls, 0 side effects", out["text"])
            self.assertEqual(out["replay"]["served_llm"], 2)
            self.assertEqual(out["replay"]["served_tool"], 1)
            self.assertIsNone(out["replay"]["desync"])
            request = box["request"]
            self.assertIn(nonce, request.context)
            self.assertEqual(request.goal, "fix the build")

    def test_mg_edit_rejects_non_tool_steps_and_second_edits(self):
        with HermesRun() as h:
            run = record_three_step_run(h)
            h.call("mg_rewind", {"run_id": run["run_id"]})
            bad = h.call("mg_edit", {"run_id": run["run_id"], "seq": 0, "args": {"path": "x"}})
            self.assertFalse(bad["ok"])
            self.assertEqual(bad["error"], "not_a_tool_step")

            good = h.call("mg_edit", {"run_id": run["run_id"], "seq": 1, "args": {"path": "config/prod.yaml"}})
            self.assertTrue(good["ok"], good)
            twice = h.call("mg_edit", {"run_id": run["run_id"], "seq": 1, "args": {"path": "y"}})
            self.assertFalse(twice["ok"])
            self.assertEqual(twice["error"], "edit_already_set")

    def test_mg_play_without_rewind_is_not_armed(self):
        with HermesRun() as h:
            out = h.call("mg_play", {"run_id": "r_missing"})
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "not_armed")


if __name__ == "__main__":
    unittest.main()
