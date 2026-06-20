# Multi-Bot Setup Guide

This repository now follows a strict identity-first multi-bot design:

- One bot equals one isolated worker process.
- Each bot must bind to exactly one `bot_id <-> hwnd <-> adb_serial <-> pid`.
- Screen capture is Windows-side only. ADB is reserved for input and lightweight health checks.
- Shared services such as GPU inference and ADB access must preserve `bot_id` and `frame_id`.

## 1. Prepare MEmu instances

1. Start each MEmu instance you plan to automate.
2. Give each instance a stable title in Multi-MEmu when possible.
3. Enable ADB debugging for every instance.

## 2. Collect the binding tuple for each bot

You need all four identifiers before a bot is allowed to start:

- `bot_id`: your logical bot name.
- `hwnd`: the Windows handle for the exact emulator window.
- `adb_serial`: the device serial returned by `adb devices`.
- `pid`: the Windows process id for that emulator instance.

Do not bind by window order, screen position, or guessed index. If the tuple is not unique, do not start that bot.

## 3. Create bindings

Use [configs/multi_bot_bindings.example.py](/D:/tienlenOPus/tienlen-bot/configs/multi_bot_bindings.example.py:1) as the template for your runtime bindings.

Before writing bindings, scan the live MEmu instances and ADB endpoints:

```bash
py -3 tools/scan_memu_adb.py
```

This prints a table with:

- `vm_index`
- `instance name`
- `adb serial`
- `android serial`
- `window title`
- `pid`
- `hwnd`

If you want starter config blocks, run:

```bash
py -3 tools/scan_memu_adb.py --as-bindings
```

If your bot already knows the target instance and only needs the exact ADB endpoint, use:

```bash
py -3 tools/scan_memu_adb.py --vm-index 203 --serial-only
py -3 tools/scan_memu_adb.py --name-contains "203H AI" --serial-only
```

Recommended fields:

- `window_title` for human-readable diagnostics.
- `identity_fingerprint` for periodic room/avatar/name rechecks.
- `metadata.priority` for admission control decisions.

## 4. Start shared services

Recommended shared services:

- `AdbBroker`: one queue per serial, low global concurrency cap.
- `InferenceService`: shared YOLO/OCR when you scale beyond a few bots.
- `SystemMonitor` and `CircuitBreaker`: detect overload and isolate failures.

ADB rules:

- Use ADB only for `tap`, `swipe`, `text`, and health checks.
- Never use `adb screencap` or `adb pull` in the hot path.
- Keep one in-flight ADB command per serial.

## 5. Start the supervisor

`BotSupervisor` is the root process. It is responsible for:

- Validating unique bindings before launch.
- Enforcing admission control.
- Starting, pausing, and restarting workers independently.
- Rechecking identity when a room/avatar fingerprint changes unexpectedly.

## 6. Worker runtime rules

Each `BotWorker` should own only its local state:

- last frame
- current game state
- decision state
- retry state
- bot-scoped logs and dumps

Hot-path safety rules:

- Queue sizes must stay bounded.
- Frame queues should keep only the latest frame.
- Do not write per-frame images to disk during live play.
- Use multi-frame consensus before taking action.
- Pause only the failing bot when capture or ADB repeatedly times out.

## 7. Scaling guidance

- Small bot count: local per-bot CPU inference is acceptable.
- Larger bot count with YOLO on GPU: use the hybrid model.

Hybrid model:

- one worker process per bot
- capture and decision inside each worker
- one shared `InferenceService`
- one shared `AdbBroker`
