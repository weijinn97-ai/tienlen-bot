# Perception Pipeline 0.1.0

Status: `CANDIDATE`

This package documents the M2.3 typed perception wiring candidate. The
pipeline converts a validated `FrameEnvelope` into a typed
`PerceptionSnapshot` through injected card, button, OCR, and turn adapters.

This is wiring and safety evidence only. It does not prove detector accuracy,
production model quality, dataset readiness, live gameplay safety, or
production qualification. The production dataset gate remains
`BLOCKED_ON_DATA`.

## Evidence

- `commands.txt`: reproducible verification commands.
- `metrics.json`: results from the verified run.
- `failures.md`: known limitations and remaining gates.

## Safety guarantees covered

- Frame identity and image shape are validated before adapter calls.
- Adapters receive image copies, so the input frame is not mutated by a
  detector.
- Detector exceptions produce structured failures.
- Button failures produce invisible, disabled `PLAY` and `PASS` states.
- Turn failures clear `turn_owner` and turn evidence.
- Adapter outputs are type-checked and deterministically ordered.
