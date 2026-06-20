# Tien Len Bot

This project targets a Windows-hosted Tien Len bot for MEmu with a multi-bot architecture that prioritizes stability and identity correctness.

## Current direction

- one bot = one isolated worker process
- explicit `bot_id <-> hwnd <-> adb_serial <-> pid` binding
- Windows-side capture only
- shared inference and ADB services behind bounded queues
- isolated recovery when one emulator instance fails

## Repository highlights

- [bot/runtime/schemas.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/schemas.py:1): shared binding and frame envelope schema
- [bot/runtime/bot_supervisor.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/bot_supervisor.py:1): lifecycle and admission control
- [bot/runtime/bot_worker.py](/D:/tienlenOPus/tienlen-bot/bot/runtime/bot_worker.py:1): per-bot actor state
- [bot/actions/adb_broker.py](/D:/tienlenOPus/tienlen-bot/bot/actions/adb_broker.py:1): serialized ADB access
- [bot/capture/capture_worker.py](/D:/tienlenOPus/tienlen-bot/bot/capture/capture_worker.py:1): state-driven capture loop
- [bot/inference/inference_service.py](/D:/tienlenOPus/tienlen-bot/bot/inference/inference_service.py:1): shared inference queue

## Key runtime rules

- do not use `adb screencap` in the hot path
- keep frame queues latest-only
- require validation and multi-frame consensus before action
- use circuit breakers and isolated restarts instead of cluster-wide recovery

## Docs

- [docs/MULTI_BOT_ARCHITECTURE.md](/D:/tienlenOPus/tienlen-bot/docs/MULTI_BOT_ARCHITECTURE.md:1)
- [docs/MULTI_BOT_SETUP_GUIDE.md](/D:/tienlenOPus/tienlen-bot/docs/MULTI_BOT_SETUP_GUIDE.md:1)
