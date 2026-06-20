# CLAUDE.md

Project-specific operating principles for AI agents working in the TienLen Bot repository.

Use this file together with higher-priority system and developer instructions. When those conflict, follow the higher-priority instruction and keep the spirit of this document.

## 1. Project Mission

We are building a Windows-hosted Tien Len bot for MEmu that is:

- stable under multi-bot load
- explicit about emulator identity
- safe to operate by a non-technical user
- observable through readable logs and a launcher UI

Current phase:

- the repository already has launcher, emulator discovery, log viewing, multi-bot scaffolding, ADB broker scaffolding, and project tracking
- the repository does not yet have a complete production gameplay loop
- do not describe the project as "finished" or "fully autonomous"

## 2. Think Before Coding

Do not assume. Do not silently choose an interpretation when the choice has consequences.

Before implementing:

- state assumptions when they affect behavior or architecture
- surface simpler options when they exist
- ask only when the ambiguity is real and risky
- prefer concrete success criteria over vague "make it work"

For multi-step work, define a short verification-oriented plan before large edits.

## 3. Simplicity First

Write the minimum code that solves the requested problem.

- no speculative features
- no abstractions for single-use code
- no configurability that the user did not ask for
- no "cleanup" outside the task
- no heavy refactor unless the user asked for it or the current design blocks the fix

If 200 lines can be 50, simplify.

## 4. Surgical Changes

Touch only what the task requires.

When editing existing code:

- preserve working behavior that the user already relies on
- match the local style and existing naming patterns
- remove only the dead code your own change creates
- mention unrelated issues instead of opportunistically rewriting them

Every changed line should trace directly to the current request or to verification for that request.

## 5. Non-Negotiable Architecture Rules

These rules are core to this repo. Do not violate them unless the user explicitly approves an architecture change.

- One bot equals one isolated worker process or actor.
- Bot identity must bind explicitly to `bot_id`, `hwnd`, `adb_serial`, and `pid`.
- Never map bots to emulator windows by screen position or window ordering.
- Do not reintroduce `adb shell screencap` or `adb pull` into the hot path.
- Capture is Windows-side and `HWND`-bound.
- Shared inference is allowed, but per-bot ownership must remain explicit through IDs.
- Shared ADB access must go through a broker or equivalent serialized control path.
- Frame queues must stay bounded and latest-frame oriented.
- Do not create shared mutable game state across bots.
- Validation and multi-frame consensus are preferred over higher FPS alone.
- Recovery should isolate the failing bot instead of restarting the entire cluster.

Reference docs:

- `docs/MULTI_BOT_ARCHITECTURE.md`
- `docs/PROJECT_BOARD.md`
- `docs/PROJECT_BOARD_VI.md`

## 6. Emulator Identity and ADB Rules

Identity correctness matters more than speed.

- prefer emulator title as the main human-readable identity in UI and logs
- keep `vm_index`, `pid`, `hwnd`, `adb_serial`, and `android_serial` available as secondary fields
- never show only IP:port in operator-facing selections if title is available
- if binding is ambiguous, do not start the bot
- if identity drifts, pause or fail safely instead of continuing on uncertain state

Any launcher, binding, or watchdog change should preserve these rules.

## 7. Logging and Operator Experience

The end user is non-technical. Logs and UI should optimize for clarity, not engineer convenience.

- prefer short structured logs over noisy repetitive spam
- title first, technical identifiers second
- summarize repetitive heartbeat or window checks when possible
- when logging a problem, include which bot, which title, and which binding failed
- keep controls obvious: scan, select, run, stop, inspect log

If a log line is technically accurate but hard for a non-technical operator to interpret, improve it.

## 8. Multi-Agent Collaboration Rules

This repository may be edited by multiple agents. Avoid collisions and hidden work.

- inspect the current worktree before editing
- never overwrite or revert unrelated user or agent changes
- prefer small atomic commits
- push only coherent, verified work
- never force-push shared branches

When work affects shared direction, coordination, or architecture:

- read `docs/PROJECT_BOARD_VI.md` or `docs/PROJECT_BOARD.md`
- if the Google Sheet tracker is in use, review `00_Overview` and `01_Task_Board`
- add a note to `02_Agent_Notes` before large or risky edits when practical
- add a row to `03_Change_Requests` when proposing significant changes
- record approved architectural choices in `05_Decisions`

Current shared tracker:

- `https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0`

If online access is unavailable, update local docs and clearly report the limitation.

## 9. Verification Standards

Work is not done at code-writing time. It is done after verification.

Typical expectations:

- for a bug fix: reproduce or isolate the bug, then verify the fix
- for parsing or data logic: add or update tests
- for UI changes: run a smoke check when possible
- for architecture or docs changes: verify references, commands, and paths
- for runtime changes: prefer the smallest realistic validation that exercises the code path

Default repo test command:

```bash
py -3 -m unittest discover -s tests -v
```

If you could not run validation, say so explicitly.

## 10. Definition of Done

A task is complete only when all relevant items below are true:

- the requested change is implemented
- obvious risks or tradeoffs are called out
- relevant tests or checks were run, or the lack of them is stated
- docs are updated if behavior or workflow changed
- shared tracking is updated if the change matters to other agents
- changes are committed and pushed when the user asks for GitHub updates

## 11. Practical Examples

Good behavior:

- "I am assuming the selected emulator title is the primary label in the UI; I will keep the ADB serial as secondary metadata."
- "This change touches launcher logging only; I will not refactor capture code."
- "This architecture proposal affects multiple agents, so I will update the project tracker and decisions log."

Bad behavior:

- silently remapping bots by window order
- adding new background services without a clear need
- reintroducing ADB screenshot capture because it is faster to prototype
- turning readable logs into raw debug dumps
- making broad refactors while fixing a narrow bug

---

These guidelines are working if:

- diffs stay focused
- emulator identity remains trustworthy
- logs get easier for the operator to read
- agents collide less often
- the repo moves steadily from launcher/scaffolding toward a verified gameplay loop
