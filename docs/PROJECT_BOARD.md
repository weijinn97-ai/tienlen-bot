# Project Board

Updated: 2026-07-25

This board is the shared source of truth for what is done, what is stable enough to use, and what should be built next.

## Mission

Build a stable Windows-hosted Tiến Lên bot system for MEmu where:

- each bot is bound to the correct emulator instance
- ADB control is reliable and isolated
- capture, perception, decision, and action are traceable by bot identity
- one failing bot does not take down the whole cluster

## Current Snapshot

Current milestone: `M1 - Runtime Foundation and Operator Control`

Meaning:

- multi-bot runtime scaffolding exists
- identity-first emulator binding exists
- launcher UI exists
- live operator logs exist
- real game perception and play logic are not finished yet

## Status Legend

- `Done`: implemented and verified locally
- `In Progress`: usable but still needs follow-up
- `Next`: recommended next build sequence
- `Blocked`: requires a dependency or decision first

## Board

| ID | Area | Status | Priority | What exists now | What is still needed |
|---|---|---|---|---|---|
| M1.1 | Core runtime architecture | Done | High | `BotSupervisor`, `BotWorker`, `FrameEnvelope`, validation, circuit breaker, ADB broker, inference service scaffold | Connect the scaffold to the real play loop |
| M1.2 | ADB hot path cleanup | Done | High | `ADBController` no longer uses screenshot capture; ADB is input and health-check only | Add richer action wrappers and retries per action type |
| M1.3 | MEmu identity scan | Done | High | Running MEmu instances can be mapped to `vm_index / title / pid / hwnd / adb_serial / android_serial` | Persist selected bindings to a project config file |
| M1.4 | Operator launcher UI | Done | High | GUI launcher can scan instances, select one, start/stop a bot session, copy binding stubs, and show live logs | Add live preview and persistent profiles |
| M1.5 | Log readability | In Progress | Medium | Logs now prefer emulator `title` over IP and watchdog logs are summarized instead of spammy | Add colored severity, filters, and save/export log support |
| M1.6 | Graceful stop behavior | Done | Medium | Launcher sends a cross-platform graceful stop request and waits before force-kill fallback; session handles SIGINT/SIGTERM | Add a live Windows operator verification record |
| M2.1 | Capture backend | In Progress | High | Window-bound capture plus read-only launcher preview exists; merged in `ff4822b` | Verify preview against a real MEmu window and document frame stability/cleanup |
| M2.2 | Snapshot validation | In Progress | High | Duplicate-card and identity checks exist in scaffold | Add real table/hand/anchor validation rules from game visuals |
| M2.3 | Perception pipeline | Next | High | Inference service contract exists | Plug in YOLO/OCR and ROI preprocessing per bot |
| M2.4 | State extraction | Next | High | Basic adapter exists | Build real game-state parser from perception outputs |
| M3.1 | Decision engine | Next | High | Local agent scaffold exists | Replace placeholder logic with real Tiến Lên decision rules |
| M3.2 | Action execution | Next | High | Action executor exists only as a stub | Map cards/buttons to coordinates and confirm actions via capture |
| M3.3 | Safe action confirmation | Next | High | Architecture expects image-based confirmation | Add post-tap verification and retry policy |
| M4.1 | Multi-bot orchestration | Next | High | Architecture supports many workers conceptually | Start multiple workers from supervisor with admission control |
| M4.2 | Resource control | In Progress | Medium | System monitor and supervisor limits exist | Add live CPU/RAM/GPU thresholds and throttling in launcher |
| M4.3 | Failure recovery | Next | Medium | Circuit breaker and isolated restart concept exist | Add automatic pause/restart policy per bot |
| M5.1 | Config persistence | Next | Medium | Binding stubs can be copied | Save selected bots and bindings to config files from the launcher |
| M5.2 | Test coverage | In Progress | Medium | Parser and core invariant tests exist | Add UI smoke tests and action/capture integration tests |

## Stable Today

These workflows are ready enough to use now:

1. Scan running MEmu instances and identify the right ADB endpoint.
2. Select an emulator by human-readable title instead of memorizing IP:port.
3. Launch a bot session from a desktop shortcut or the launcher script.
4. Watch live bot logs in one place while verifying title, HWND, PID, and ADB health.

## Not Done Yet

These are the biggest missing pieces before the bot can play a real match:

1. Real frame capture pipeline inside the live operator flow.
2. Real card/button/turn detection from frames.
3. Real decision-making based on game state.
4. Real tap/swipe execution confirmed by image feedback.

## Recommended Next Sequence

Build in this order to keep momentum and reduce rework:

1. `M2.1` Live MEmu capture verification and preview soak.
2. `M2.3` Perception pipeline wiring with ROI preprocessing.
3. `M2.4` State extraction from perception outputs.
4. `M2.4` State extraction from perception outputs.
5. `M3.2` Action execution with coordinate mapping.
6. `M3.3` Post-action confirmation by capture.
7. `M3.1` Real decision engine.
8. `M4.1` Supervisor-driven multi-bot startup.

## Agent Work Split

If multiple agents work in parallel, this split is the safest:

| Lane | Suggested ownership | Safe to work in parallel with |
|---|---|---|
| A | launcher UX, logs, config persistence | B, C |
| B | capture backend and preview | A, C |
| C | perception and state extraction | A, B |
| D | action execution and confirmation | A after capture/state contracts are fixed |
| E | multi-bot supervisor and resource control | A, C after contracts stabilize |

## Contract Files Other Agents Should Respect

- [bot/runtime/schemas.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/schemas.py:1)
- [bot/runtime/validation.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/validation.py:1)
- [bot/actions/adb_broker.py](/D:/tienlenOPus/tienlen-bot/bot/actions/adb_broker.py:1)
- [bot/discovery/adb_discovery.py](/D:/tienlenOPus/tienlen-bot/bot/discovery/adb_discovery.py:1)
- [bot/ui/launcher_app.py](/D:/tienlenOPus/tienlen-bot/bot/ui/launcher_app.py:1)

## Known Risks

1. The current live session is still a watchdog session, not a true game-playing bot.
2. The window capture scaffold is not yet the final production capture backend.
3. Stop behavior still needs a soft shutdown path.
4. Coordinate-based action logic will need calibration per emulator layout.

## Definition Of The Next Meaningful Demo

The next meaningful demo should prove all of the following in one launcher session:

1. Show a live frame preview for the chosen emulator.
2. Detect at least one stable game-state element from that frame.
3. Log the parsed state in the launcher.
4. Execute one safe test action and confirm it visually.
