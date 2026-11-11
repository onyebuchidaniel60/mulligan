# Operator Intake â€” Mulligan

| Input | Status | Source | Notes |
|---|---|---|---|
| Project = Mulligan | DECIDED | operator | counterfactual replay for Hermes |
| Scope = MVP per PROJECT_SPEC.md | DECIDED | operator | |
| Architecture fixed per ARCHITECTURE.md | DECIDED | operator | |
| OPENROUTER_API_KEY | HAVE | operator | set in ~/.hermes/.env |
| Hermes installed | CONFIRM | operator | run `hermes --version` |
| Demo failure case = read_file ENOENT | DECIDED | operator | non-dangerous, no approvals |
| Reference images | N/A | â€” | CLI plugin |
| UI skill (stageshow) | N/A | â€” | CLI plugin |
| Frontend / preview URL | N/A | â€” | CLI plugin |
| Database / auth / payments | N/A | â€” | CLI plugin |
| Budget ceiling | $0 | operator | stdlib only |
| Production authority | N/A | operator | catalog PR only |
| API surface answers (a)-(d) | BLOCKER | developer guide | Phase 0 |

## Phase 0 blocker detail
(a) ctx.register_middleware signature + callback kwargs
(b) ctx.subagent_lifecycle.launch / SubagentLaunchRequest fields + child state visibility
(c) Middleware ordering relative to approvals
(d) ctx.register_tool handler signature + return contract

Resolve all four before any code is written.
