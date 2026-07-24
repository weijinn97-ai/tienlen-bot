# Capture Acceptance 0.1.0

## Scope

This evidence validates the read-only Windows capture backend and launcher preview input on the connected MEmu window. It does not validate perception accuracy, ADB actions, gameplay, or production readiness.

## Environment

- Date: 2026-07-25
- Window: `11JP - 202H AI`
- HWND: `7474714`
- ADB serial observed read-only: `127.0.0.1:23523`
- Capture frames: BGR `uint8`

## Results

- Single capture: `shape=(753, 1321, 3)`
- 20-frame soak: `20/20` captured successfully
- Unique shapes: `[(753, 1321, 3)]`
- Unique frame hashes: `2` (screen changed during capture; no frozen-frame false pass)
- Average capture time: `38.70 ms`
- Maximum capture time: `49.42 ms`
- Frame conversion unit tests: `2/2 OK`

## Safety boundary

No tap, swipe, text input, ADB action, gameplay action, training, or network inference was performed. The capture result is evidence for M2.1 only; `MOD-PERCEPTION` remains `IN_PROGRESS` and production qualification remains blocked.
