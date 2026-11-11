"""The six Mulligan tools. Every handler returns a JSON string and never raises."""

from __future__ import annotations

import functools
import json
import time
from typing import Any, Callable

from . import mg_state as state


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _ok(text: str, **data: Any) -> str:
    return _json({"ok": True, "text": text, **data})


def _err(code: str, message: str, **data: Any) -> str:
    text = f"mulligan: {code} — {message}"
    return _json({"ok": False, "error": code, "message": message, "text": text, **data})


def _safe(fn: Callable) -> Callable:
    """Tool handlers must never raise (developer guide, Step 4 rule 3)."""

    @functools.wraps(fn)
    def wrapper(args: Any = None, **kwargs: Any) -> str:
        try:
            return fn(args if isinstance(args, dict) else {}, **kwargs)
        except state.TraceError as exc:
            return _err(str(exc), "trace store refused the operation")
        except Exception as exc:  # noqa: BLE001 - contract: return JSON, never raise
            return _err("internal_error", f"{type(exc).__name__}: {exc}")

    return wrapper


def _session(kwargs: dict) -> str:
    return str(kwargs.get("session_id") or "")


def _short(value: Any, limit: int = 48) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _step_label(step: dict) -> str:
    if step.get("type") == "llm_call":
        assistant = step.get("assistant") or {}
        calls = [c.get("name") for c in (assistant.get("tool_calls") or []) if c.get("name")]
        content = (assistant.get("content") or "").strip()
        if calls:
            return "decides " + ", ".join(calls)
        return "reply " + _short(content, 60) if content else "reply (empty)"
    name = step.get("tool_name") or "?"
    return f"{name}({_short(step.get('args'), 60)})"


# ------------------------------------------------------------------------- tools


@_safe
def mg_list(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    root, err = state.trace_root()
    if root is None:
        return _err(err or "trace_dir_unavailable", "recording is disabled for this profile")
    runs = state.list_runs()
    if not runs:
        return _ok(
            f"No recorded runs in {root}.\nRun something with the plugin enabled, then mg_list again.",
            trace_dir=str(root),
            runs=[],
        )
    lines = [f"{len(runs)} run(s) in {root}", ""]
    lines.append(f"{'run_id':<26} {'steps':>5}  {'branch':<22} goal")
    for run in runs:
        branch = f"of {run['branch_of']} @ {run['branch_at']}" if run.get("branch_of") else "—"
        lines.append(f"{run['run_id']:<26} {run['steps']:>5}  {branch:<22} {_short(run.get('goal') or '', 50)}")
    return _ok("\n".join(lines), trace_dir=str(root), runs=runs)


@_safe
def mg_inspect(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    run_id = str(args.get("run_id") or "").strip()
    if not run_id:
        return _err("missing_run_id", "pass the run_id from mg_list")
    limit = int(args.get("limit") or 40)
    records = state.read_trace(run_id)
    header = state.load_header(records)
    steps = state.annotate(records)
    if not steps:
        return _ok(f"Run {run_id} has no steps.", run_id=run_id, steps=[])

    lines = []
    goal = (header.get("goal") or "").strip()
    lines.append(f"run {run_id} · {len(steps)} steps" + (f" · {_short(goal, 70)}" if goal else ""))
    if header.get("branch_of"):
        lines.append(f"branch of {header['branch_of']} at step {header.get('branch_at')}")
    lines.append("")
    lines.append(f"{'seq':>3}  {'kind':<4}  {'step':<64} status")
    failing = None
    for step in steps[:limit]:
        status = step.get("status") or ("ok" if step.get("type") == "llm_call" else "")
        if status == "error" and failing is None:
            failing = step.get("seq")
        lines.append(f"{int(step.get('seq', 0)):>3}  {step.get('type', '?')[:4]:<4}  {_step_label(step):<64} {status}")
    if len(steps) > limit:
        lines.append(f"… {len(steps) - limit} more (pass limit= to see them)")
    if failing is not None:
        lines.append("")
        lines.append(f"first failing step: {failing} — mg_rewind --to {failing} then mg_edit and mg_play")
    return _ok(
        "\n".join(lines),
        run_id=run_id,
        header=header,
        step_count=len(steps),
        first_failure=failing,
        steps=steps[:limit],
    )


@_safe
def mg_rewind(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    run_id = str(args.get("run_id") or "").strip()
    if not run_id:
        return _err("missing_run_id", "pass the run_id from mg_list")
    session_id = _session(kwargs)
    if not session_id:
        return _err("no_session", "mg_rewind needs a chat session id; call it from a normal session")

    records = state.read_trace(run_id)
    header = state.load_header(records)
    steps = state.load_steps(records)
    if not steps:
        return _err("empty_run", f"run {run_id} has no llm/tool steps to replay")

    raw_to = args.get("to")
    branch_at = len(steps) if raw_to is None else int(raw_to)
    if branch_at < 0 or branch_at > len(steps):
        return _err("bad_branch_point", f"to must be between 0 and {len(steps)}")

    pending = state.PendingReplay(
        parent_session_id=session_id,
        run_id=run_id,
        nonce=state.new_nonce(),
        steps=steps,
        branch_at=branch_at,
        edit=None,
    )
    state.arm(pending)
    parent = state.get_or_create(session_id, state.LIVE)
    parent.mode = state.ARMED

    served = branch_at
    live = len(steps) - branch_at
    lines = [
        f"Armed replay of {run_id}: steps 0..{served - 1} served from the record, live from {branch_at}.",
        f"{served} step(s) deterministic · {live} live step(s) · source goal: {_short(header.get('goal') or '—', 60)}",
        "Next: mg_edit (optional), then mg_play.",
    ]
    return _ok(
        "\n".join(lines),
        run_id=run_id,
        branch_at=branch_at,
        served_steps=served,
        live_steps=live,
        steps=len(steps),
    )


@_safe
def mg_edit(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    run_id = str(args.get("run_id") or "").strip()
    if not run_id:
        return _err("missing_run_id", "pass the run_id from mg_rewind")
    session_id = _session(kwargs)
    pending = state.pending()
    if pending is None or pending.run_id != run_id or pending.parent_session_id != session_id:
        return _err("not_armed", "run mg_rewind for this run first")

    try:
        seq = int(args.get("seq"))
    except (TypeError, ValueError):
        return _err("bad_seq", "seq must be the integer step number from mg_inspect")
    new_args = args.get("args")
    if not isinstance(new_args, dict):
        return _err("bad_args", "args must be a JSON object of tool arguments")

    step = next((s for s in pending.steps if int(s.get("seq", -1)) == seq), None)
    if step is None:
        return _err("unknown_step", f"run {run_id} has no step {seq}")
    if step.get("type") != "tool_call":
        return _err("not_a_tool_step", f"step {seq} is a {step.get('type')}; only tool arguments can be edited")
    if pending.edit is not None:
        return _err("edit_already_set", f"step {pending.edit.get('seq')} is already edited; one edit per branch")

    tool = args.get("tool")
    if tool and tool != step.get("tool_name"):
        return _err("tool_mismatch", f"step {seq} calls {step.get('tool_name')}, not {tool}")

    pending.edit = {"seq": seq, "tool": step.get("tool_name"), "args": new_args}
    old = step.get("args")
    lines = [
        f"Edit armed at step {seq}: {step.get('tool_name')}",
        f"  before: {_short(old, 200)}",
        f"  after : {_short(new_args, 200)}",
        f"Replay will serve steps 0..{seq - 1}, then run step {seq} live with the edited arguments.",
    ]
    return _ok(
        "\n".join(lines),
        run_id=run_id,
        seq=seq,
        tool=step.get("tool_name"),
        before=old,
        after=new_args,
        served_steps=seq,
    )


@_safe
def mg_play(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    run_id = str(args.get("run_id") or "").strip()
    if not run_id:
        return _err("missing_run_id", "pass the run_id from mg_rewind")
    session_id = _session(kwargs)
    pending = state.pending()
    if pending is None or pending.run_id != run_id or pending.parent_session_id != session_id:
        return _err("not_armed", "run mg_rewind for this run first")

    timeout = float(args.get("timeout_seconds") or 600)
    branch_at = pending.branch_at
    edit = pending.edit
    banner = _banner(pending, edit)

    service = getattr(ctx, "subagent_lifecycle", None)
    if service is None:
        return _err("no_subagent_api", "ctx.subagent_lifecycle is unavailable in this Hermes build")

    try:
        from agent.subagent_lifecycle import SubagentLaunchRequest
    except Exception as exc:  # pragma: no cover - version guard
        return _err("no_subagent_api", f"SubagentLaunchRequest import failed: {exc}")

    goal = _goal_for(pending)
    context = (
        f"This is a Mulligan replay of recorded run {run_id}. {pending.nonce}\n"
        f"{banner}\n"
        "Continue the original task. Do not ask the user questions; act with the tools available."
    )
    request = SubagentLaunchRequest(
        goal=goal,
        context=context,
        role="leaf",
        correlation_id=f"mulligan-{run_id}-{pending.nonce[-8:]}",
        metadata={"mulligan_run_id": run_id, "mulligan_branch_at": branch_at},
    )

    started = time.time()
    try:
        handle = service.launch(request)
    except Exception as exc:  # noqa: BLE001 - typed failure, state preserved
        return _err(
            "launch_failed",
            f"{type(exc).__name__}: {exc}",
            hint="the armed replay is preserved; fix the cause and call mg_play again",
            banner=banner,
        )

    terminal = service.wait(handle, timeout_seconds=timeout)
    result = service.result(handle)
    duration = time.time() - started

    child = state.find_child_state(session_id, run_id)
    summary = child.summary() if child else None
    status = getattr(getattr(result, "state", None), "value", None) or str(getattr(result, "state", ""))
    summary_text = getattr(result, "summary", None)
    error = getattr(result, "error_message", None)

    lines = [banner, "", f"child session {handle.subagent_id} · {status} · {duration:.1f}s"]
    if summary:
        lines.append(
            f"served {summary['served_llm']} llm + {summary['served_tool']} tool step(s) from the record "
            f"(0 provider calls, 0 side effects)"
        )
        lines.append(f"live {summary['live_llm']} llm + {summary['live_tool']} tool step(s)")
        if summary.get("run_id"):
            lines.append(f"branch trace: {summary['run_id']}")
        if summary.get("desync"):
            lines.append(f"DESYNC at step {summary['desync'].get('seq')}: {summary['desync']}")
        if summary.get("error"):
            lines.append(f"trace error: {summary['error']}")
    else:
        lines.append("no replay state was bound to the child session — the child ran without the record")
    if summary_text:
        lines.append("")
        lines.append(str(summary_text)[:1200])
    if error:
        lines.append(f"child error: {error}")

    return _ok(
        "\n".join(lines),
        run_id=run_id,
        child_session_id=handle.subagent_id,
        status=status,
        duration_s=round(duration, 2),
        replay=summary,
        branch_run_id=(summary or {}).get("run_id"),
        summary=summary_text,
        error=error,
        banner=banner,
    )


def _goal_for(pending: state.PendingReplay) -> str:
    try:
        header = state.load_header(state.read_trace(pending.run_id))
    except state.TraceError:
        header = {}
    goal = (header.get("goal") or "").strip()
    if goal:
        return goal[:4000]
    return "Continue the task that produced the recorded run."


def _banner(pending: state.PendingReplay, edit: dict | None) -> str:
    rule = "=" * 78
    branch = f"live from step {pending.branch_at}"
    if edit:
        branch = f"edit at step {edit['seq']}, live from there"
    return "\n".join(
        [
            rule,
            f" MULLIGAN REPLAY · {pending.run_id} · {pending.branch_at} step(s) served, {branch}",
            " Served steps are side-effect free: 0 provider calls, 0 tool invocations.",
            " The branch after the cut-off runs LIVE — tools and approvals behave normally.",
            rule,
        ]
    )


@_safe
def mg_diff(args: dict, ctx: Any = None, **kwargs: Any) -> str:
    run_a = str(args.get("run_a") or "").strip()
    run_b = str(args.get("run_b") or "").strip()
    if not run_a or not run_b:
        return _err("missing_run", "pass run_a and run_b")

    a_records = state.read_trace(run_a)
    b_records = state.read_trace(run_b)
    a_steps = state.annotate(a_records)
    b_steps = state.annotate(b_records)
    a_header = state.load_header(a_records)
    b_header = state.load_header(b_records)

    # A branch only records the steps it ran live; the deterministic prefix it served
    # belongs to the parent run, so compare against that prefix rather than calling it
    # a divergence.
    a_view = _with_branch_prefix(a_steps, a_header, run_b, b_steps)
    b_view = _with_branch_prefix(b_steps, b_header, run_a, a_steps)

    divergence = _first_divergence(a_view, b_view)
    a_fail = _first_failure(a_view)
    b_fail = _first_failure(b_view)
    b_desync = next((r for r in b_records if r.get("type") == "desync"), None)
    served = int(b_header.get("branch_at") or 0)

    lines = [
        f"A {run_a:<24} {len(a_view):>3} steps · {'FAILED at ' + str(a_fail) if a_fail is not None else 'no failing step'}",
        f"B {run_b:<24} {len(b_view):>3} steps · {'FAILED at ' + str(b_fail) if b_fail is not None else 'no failing step'}",
        "",
    ]
    if b_header.get("branch_of"):
        lines.append(
            f"B is a branch of {b_header['branch_of']} at step {served}: "
            f"steps 0..{served - 1} served deterministically, {len(b_steps)} executed live."
        )
    if divergence is None:
        lines.append("first divergence: none — the runs agree on every compared step")
    else:
        lines.append(f"first divergence: step {divergence['seq']} ({divergence['why']})")
        lines.append(f"  A: {divergence['a']}")
        lines.append(f"  B: {divergence['b']}")
    if b_desync:
        lines.append(f"DESYNC recorded in B at step {b_desync.get('seq')}: expected {b_desync.get('expected')}, saw {b_desync.get('actual')}")

    width = 68
    lines.append("")
    lines.append(f"{'#':>3}  {'A':<{width}}  B")
    for index in range(min(len(a_view), len(b_view))):
        left = _step_label(a_view[index])
        right = _step_label(b_view[index])
        mark = " " if left == right else "≠"
        lines.append(f"{a_view[index].get('seq', index):>3} {mark}{left[:width]:<{width}}  {right[:width]}")

    return _ok(
        "\n".join(lines),
        run_a=run_a,
        run_b=run_b,
        steps_a=len(a_view),
        steps_b=len(b_view),
        first_divergence=divergence,
        first_failure_a=a_fail,
        first_failure_b=b_fail,
        served_steps=served,
        live_steps=len(b_steps),
        desync=b_desync,
    )


def _with_branch_prefix(steps: list[dict], header: dict, other_run: str, other_steps: list[dict]) -> list[dict]:
    """Prepend the parent's served prefix when ``steps`` is a branch of ``other_run``."""
    if header.get("branch_of") != other_run:
        return steps
    try:
        cut = int(header.get("branch_at"))
    except (TypeError, ValueError):
        return steps
    return other_steps[:cut] + steps


def _first_failure(steps: list[dict]) -> int | None:
    for step in steps:
        if step.get("status") == "error":
            return int(step.get("seq", -1))
    return None


def _first_divergence(a_steps: list[dict], b_steps: list[dict]) -> dict | None:
    for index in range(min(len(a_steps), len(b_steps))):
        left = _fingerprint(a_steps[index])
        right = _fingerprint(b_steps[index])
        if left == right:
            continue
        return {
            "seq": int(b_steps[index].get("seq", index)),
            "why": _why(a_steps[index], b_steps[index]),
            "a": _step_label(a_steps[index]),
            "b": _step_label(b_steps[index]),
        }
    if len(a_steps) != len(b_steps):
        longer = b_steps if len(b_steps) > len(a_steps) else a_steps
        step = longer[min(len(a_steps), len(b_steps))]
        return {
            "seq": int(step.get("seq", min(len(a_steps), len(b_steps)))),
            "why": "one run is longer",
            "a": f"{len(a_steps)} steps",
            "b": f"{len(b_steps)} steps",
        }
    return None


def _fingerprint(step: dict) -> tuple:
    if step.get("type") == "tool_call":
        return ("tool", step.get("tool_name"), step.get("args_digest"))
    assistant = step.get("assistant") or {}
    calls = tuple((c.get("name"), c.get("arguments")) for c in (assistant.get("tool_calls") or []))
    return ("llm", (assistant.get("content") or "").strip()[:200], calls)


def _why(left: dict, right: dict) -> str:
    if left.get("type") != right.get("type"):
        return f"A is {left.get('type')}, B is {right.get('type')}"
    if left.get("type") == "tool_call":
        if left.get("tool_name") != right.get("tool_name"):
            return f"different tool ({left.get('tool_name')} vs {right.get('tool_name')})"
        return "different tool arguments"
    return "different model decision"
