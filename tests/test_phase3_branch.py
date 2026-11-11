"""Phase 3 acceptance: edit a decision, branch live, record the branch to a new run."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from harness import HermesRun, response, tool_result


class _ScriptedService:
    """Fake ctx.subagent_lifecycle that runs the child script inline."""

    def __init__(self, script):
        self.script = script
        self.request = None

    def launch(self, request):
        self.request = request
        self.script(request)
        return SimpleNamespace(subagent_id="sub-branch")

    def wait(self, handle, timeout_seconds=None):
        return SimpleNamespace(timed_out=False)

    def result(self, handle):
        return SimpleNamespace(state=SimpleNamespace(value="succeeded"), summary="read config/prod.yaml", error_message=None)


def record_failing_run(h: HermesRun, session: str = "sess-parent") -> str:
    """llm -> read_file(dev) FAILS -> llm gives up. """
    h.llm(session, {"messages": [{"role": "user", "content": "deploy the service"}]},
          response(tool_calls=[{"id": "call_cfg", "name": "read_file", "arguments": {"path": "config/dev.yaml"}}]), [])
    h.tool(session, "read_file", {"path": "config/dev.yaml"},
           tool_result(False, error="FileNotFoundError: config/dev.yaml"), "call_cfg", [])
    h.llm(session, {"messages": [{"role": "user", "content": "deploy the service"}]},
          response("I could not read the config; stopping."), [])
    return h.state.list_runs()[0]["run_id"]


class TestBranch(unittest.TestCase):
    def test_edit_at_failing_step_makes_the_branch_succeed(self):
        with HermesRun() as h:
            run_id = record_failing_run(h)
            steps = h.state.load_steps(h.state.read_trace(run_id))
            failing = h.state.annotate(h.state.read_trace(run_id))[1]
            self.assertEqual(failing["status"], "error")
            self.assertEqual(failing["seq"], 1)

            rewound = h.call("mg_rewind", {"run_id": run_id, "to": 1})
            self.assertTrue(rewound["ok"], rewound)
            edited = h.call("mg_edit", {"run_id": run_id, "seq": 1, "args": {"path": "config/prod.yaml"}})
            self.assertTrue(edited["ok"], edited)

            provider: list = []
            executed: list = []

            def script(request):
                nonce = request.context.split("MULLIGAN-")[1].split()[0]
                child = "sess-branch"
                # step 0 is served: the model still asks for config/dev.yaml ...
                served = h.llm(child, {"messages": [{"role": "user", "content": request.context}]},
                               response("LIVE"), provider)
                self.assertEqual(provider, [])
                args = json.loads(served.choices[0].message.tool_calls[0].function.arguments)
                self.assertEqual(args["path"], "config/dev.yaml")
                # ... but the branch edit rewrites the arguments before execution.
                result = h.tool(child, "read_file", args,
                                tool_result(True, content="service: web\nport: 8080"),
                                served.choices[0].message.tool_calls[0].id, executed)
                self.assertEqual(executed, [("read_file", {"path": "config/prod.yaml"})])
                self.assertTrue(json.loads(result)["ok"])
                # everything after the branch point is live
                h.llm(child, {"messages": [{"role": "user", "content": "continue"}]},
                      response("Deploying with config/prod.yaml."), provider)

            service = _ScriptedService(script)
            out = json.loads(
                h.module.mg_tools.mg_play(
                    {"run_id": run_id}, ctx=SimpleNamespace(subagent_lifecycle=service), session_id="sess-parent"
                )
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(len(executed), 1, "exactly the edited step runs live")
            self.assertEqual(out["replay"]["served_llm"], 1)
            self.assertEqual(out["replay"]["served_tool"], 0)
            self.assertEqual(out["replay"]["live_tool"], 1)
            self.assertEqual(out["replay"]["live_llm"], 1)
            self.assertIsNone(out["replay"]["desync"])

            branch_id = out["branch_run_id"]
            self.assertIsNotNone(branch_id)
            header = h.state.load_header(h.state.read_trace(branch_id))
            self.assertEqual(header["branch_of"], run_id)
            self.assertEqual(header["branch_at"], 1)
            branch_steps = h.state.load_steps(h.state.read_trace(branch_id))
            self.assertEqual([s["seq"] for s in branch_steps], [1, 2], "branch starts at the edit point")
            self.assertEqual(branch_steps[0]["tool_name"], "read_file")
            self.assertEqual(branch_steps[0]["args"], {"path": "config/prod.yaml"})
            self.assertEqual(json.loads(branch_steps[0]["result"])["ok"], True)

            # The original trace is untouched (append-only, never rewritten).
            self.assertEqual(len(h.state.load_steps(h.state.read_trace(run_id))), 3)

            diff = json.loads(h.module.mg_tools.mg_diff(
                {"run_a": run_id, "run_b": branch_id}, session_id="sess-parent"))
            self.assertTrue(diff["ok"], diff)
            self.assertEqual(diff["first_divergence"]["seq"], 1)
            self.assertEqual(diff["first_divergence"]["why"], "different tool arguments")
            self.assertEqual(diff["first_failure_a"], 1)
            self.assertIsNone(diff["first_failure_b"])
            self.assertEqual(diff["served_steps"], 1)

    def test_edit_outside_the_branch_window_is_still_recorded_honestly(self):
        with HermesRun() as h:
            run_id = record_failing_run(h)
            h.call("mg_rewind", {"run_id": run_id, "to": 3})  # full replay, nothing live
            h.call("mg_edit", {"run_id": run_id, "seq": 1, "args": {"path": "config/prod.yaml"}})

            provider: list = []

            def script(request):
                child = "sess-full"
                h.llm(child, {"messages": [{"role": "user", "content": request.context}]}, response("LIVE"), provider)
                h.tool(child, "read_file", {"path": "config/dev.yaml"}, "LIVE", "call_cfg", [])
                h.llm(child, {"messages": [{"role": "user", "content": "go"}]}, response("LIVE"), provider)

            out = json.loads(h.module.mg_tools.mg_play(
                {"run_id": run_id},
                ctx=SimpleNamespace(subagent_lifecycle=_ScriptedService(script)),
                session_id="sess-parent",
            ))
            self.assertTrue(out["ok"], out)
            # The edit is beyond the branch window, so the recorded steps are served as-is.
            self.assertEqual(out["replay"]["served_tool"], 1)
            self.assertEqual(out["replay"]["live_tool"], 0)
            self.assertEqual(provider, [])


if __name__ == "__main__":
    unittest.main()
