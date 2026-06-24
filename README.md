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
- [docs/PROJECT_BOARD.md](/D:/tienlenOPus/tienlen-bot/docs/PROJECT_BOARD.md:1)
- [docs/PROJECT_BOARD_VI.md](/D:/tienlenOPus/tienlen-bot/docs/PROJECT_BOARD_VI.md:1)
- [docs/GOOGLE_SHEET_TRACKER_VI.md](/D:/tienlenOPus/tienlen-bot/docs/GOOGLE_SHEET_TRACKER_VI.md:1)

## ADB Scan

Use the scanner below to map each running MEmu instance to its exact ADB endpoint before creating bindings:

```bash
py -3 tools/scan_memu_adb.py
```

To generate `BotBinding` stubs directly:

```bash
py -3 tools/scan_memu_adb.py --as-bindings
```

To get only the exact ADB serial for one chosen instance:

```bash
py -3 tools/scan_memu_adb.py --vm-index 203 --serial-only
py -3 tools/scan_memu_adb.py --name-contains "203H AI" --serial-only
```

## Launcher

The repo now includes a Windows launcher UI with:

- emulator selection
- one-click bot start and stop
- live detailed log panel
- copyable `BotBinding` stub for the selected instance

Start it with:

```bash
py -3 tools/launch_bot_ui.py
```

Or on this machine, use:

```bash
launch_bot_ui.cmd
```

## Online Tracker

The project also has a shared Google Sheet tracker for humans and agents:

- [docs/GOOGLE_SHEET_TRACKER_VI.md](/D:/tienlenOPus/tienlen-bot/docs/GOOGLE_SHEET_TRACKER_VI.md:1)

If the sheet link is publicly editable, you can seed the standard tabs directly from this repo:

```bash
py -3 -m pip install playwright
py -3 tools/seed_google_sheet_public.py --sheet-url "https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0"
```

## Screenshot Intake

For user-provided screenshots that need to stay accessible to multiple agents before labeling:

```bash
py -3 tools/import_user_screenshots.py --batch-name your_batch_name --files "C:\path\shot1.png" "C:\path\shot2.png"
py -3 tools/export_image_index_csv.py
```

See:

- [data/README.md](/D:/tienlenOPus/tienlen-bot/data/README.md:1)
- [docs/GOOGLE_SHEET_TRACKER_VI.md](/D:/tienlenOPus/tienlen-bot/docs/GOOGLE_SHEET_TRACKER_VI.md:1)
