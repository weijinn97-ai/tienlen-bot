# Multi-Bot Architecture

This document captures the current target architecture for stable multi-bot execution on Windows and MEmu.

## Core principles

- One bot is one independent actor.
- Identity is explicit and must be verified before launch.
- Shared services may optimize compute, but they must never blur per-bot ownership.
- Failure isolation is more important than raw throughput.

## Runtime layout

- `BotSupervisor`
  - owns lifecycle, registry, admission control, and isolated restart
- `BotWorker`
  - owns game state, last frame, decision state, retries, and bot-scoped logs
- `CaptureWorker`
  - captures only the bound `HWND`
  - keeps latest-frame only
  - changes capture rate by state
- `InferenceService`
  - shared YOLO/OCR path
  - preserves `bot_id` and `frame_id`
- `AdbBroker`
  - one queue per serial
  - one in-flight command per device
- `SystemMonitor` and `CircuitBreaker`
  - expose resource metrics
  - stop local failure from becoming a cluster-wide crash

## Identity model

Every bot must be bound to a unique tuple:

- `bot_id`
- `hwnd`
- `adb_serial`
- `pid`

Optional fingerprint fields can be used for periodic identity rechecks:

- room id
- avatar hash
- player name hash

## Capture model

Target production backend:

- primary: Windows Graphics Capture
- fallback: Desktop Duplication API

Current repository scaffold:

- `bot.capture.windows_capture.WindowsCapture` is already `HWND`-bound
- hot path is Windows-side only
- no ADB screenshot path remains in `ADBController`

## Safety rules

- `Queue bounded`: image queues must be size `1` or `2`
- `No shared mutable state`: each worker owns its own state only
- `No disk in hot path`: dumps happen only for scoped failures
- `No multi-adb burst`: serialize by device and cap globally
- `Circuit breaker`: pause the failing bot after repeated timeouts
- `Identity recheck`: fingerprint room/avatar/name periodically
- `Recovery isolated`: restart only the affected bot

## Files added in this repo

- [bot/runtime/schemas.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/schemas.py:1)
- [bot/runtime/bot_supervisor.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/bot_supervisor.py:1)
- [bot/runtime/bot_worker.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/bot_worker.py:1)
- [bot/runtime/validation.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/validation.py:1)
- [bot/actions/adb_broker.py](/D:/tienlenOPus/tienlen-bot/bot/actions/adb_broker.py:1)
- [bot/capture/capture_worker.py](/D:/tienlenOPus/tienlen-bot/bot/capture/capture_worker.py:1)
- [bot/inference/inference_service.py](/D:/tienlenOPus/tienlen-bot/bot/inference/inference_service.py:1)
- [bot/stability/watchdog.py](/D:/tienlenOPus/tienlen-bot/bot/stability/watchdog.py:1)
