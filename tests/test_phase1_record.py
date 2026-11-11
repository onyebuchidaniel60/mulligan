"""Phase 1 acceptance: a 3-step scripted run produces a well-formed trace."""

from __future__ import annotations

import json
import unittest

from harness import HermesRun, response, tool_result


class TestRecordOnly(unittest.TestCase):
    def test_three_step_run_writes_well_formed_trace(self):
        with HermesRun() as h:
            provider_calls: list = []
            tool_calls: list = []
            session = "sess-record-1"

            first = response(tool_calls=[{"id": "call_1", "name": "read_file", "arguments": {"path": "config/dev.yaml"}}])
            h.llm(session, {"messages": [{"role": "user", "content": "fix the build"}]}, first, provider_calls)
            h.tool(session, "read_file", {"path": "config/dev.yaml"}, tool_result(False, error="FileNotFoundError"), "call_1", tool_calls)
            h.llm(session, {"messages": [{"role": "user", "content": "fix the build"}, {"role": "assistant", "content": None}]}, response("I could not read the config."), provider_calls)

            self.assertEqual(len(provider_calls), 2)
            self.assertEqual(len(tool_calls), 1)

            runs = json.loads(json.dumps(h.state.list_runs()))
            self.assertEqual(len(runs), 1, "one trace file per session")
            run = runs[0]
            self.assertEqual(run["steps"], 3)
            self.assertEqual(run["session_id"], session)
            self.assertEqual(run["goal"], "fix the build")

            records = h.state.read_trace(run["run_id"])
            self.assertEqual(records[0]["type"], "header")
            self.assertEqual(records[0]["v"], 1)
            self.assertEqual([r["type"] for r in records if r["type"] in ("llm_call", "tool_call")],
                             ["llm_call", "tool_call", "llm_call"])
            steps = h.state.load_steps(records)
            self.assertEqual([s["seq"] for s in steps], [0, 1, 2])
            self.assertEqual(steps[1]["tool_name"], "read_file")
            self.assertEqual(json.loads(steps[1]["result"])["error"], "FileNotFoundError")
            self.assertEqual(steps[0]["assistant"]["tool_calls"][0]["name"], "read_file")
            self.assertEqual(steps[2]["assistant"]["content"], "I could not read the config.")

            # Append-only: every line is valid JSON and nothing was rewritten.
            path = h.state.run_path(run["run_id"])
            lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            self.assertTrue(all(isinstance(line, dict) for line in lines))
            self.assertEqual(sum(1 for line in lines if line["type"] == "tool_status"), 1,
                             "post_tool_call appends a status annotation, never a rewrite")

    def test_mulligan_own_tools_are_not_recorded(self):
        with HermesRun() as h:
            session = "sess-record-2"
            h.llm(session, {"messages": [{"role": "user", "content": "list runs"}]}, response("ok"), [])
            before = len(h.state.read_trace(h.state.list_runs()[0]["run_id"]))
            h.tool(session, "mg_list", {}, tool_result(True), "call_mg", [])
            after = len(h.state.read_trace(h.state.list_runs()[0]["run_id"]))
            self.assertEqual(before, after, "mg_* calls must not pollute the trace")

    def test_trace_dir_is_inside_hermes_home(self):
        with HermesRun() as h:
            root, err = h.state.trace_root()
            self.assertIsNone(err)
            self.assertTrue(str(root).startswith(str(h.home)))
            self.assertEqual(root.name, "replay-traces")

    def test_trace_dir_outside_home_is_refused(self):
        with HermesRun() as h:
            import os

            os.environ["MULLIGAN_TRACE_DIR"] = "/tmp/definitely-not-hermes-home"
            try:
                root, err = h.state.trace_root()
                self.assertIsNone(root)
                self.assertEqual(err, "trace_dir_outside_hermes_home")
            finally:
                os.environ.pop("MULLIGAN_TRACE_DIR", None)


if __name__ == "__main__":
    unittest.main()
