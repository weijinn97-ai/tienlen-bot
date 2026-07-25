# M2.3 Perception Pipeline 01

## Objective

Create a deterministic, injectable perception pipeline that converts one
validated `FrameEnvelope` image into a typed `PerceptionSnapshot` using the
existing card, button, OCR, and hybrid turn-owner adapters.

This task is wiring only. It must not train, load production weights, capture
new data, call ADB input, or change contracts.

## Allowed paths

- `bot/perception/pipeline.py`
- `bot/perception/__init__.py`
- `tests/test_perception_pipeline.py`
- `docs/acceptance/perception/0.1.0/**`
- `M2_3_PERCEPTION_PIPELINE_OUTPUT/**`

## Forbidden operations

- Do not modify contracts, serialization, runtime worker behavior, action code,
  capture code, UI evaluator, existing detectors, dataset files, or module
  registry.
- Do not train or commit model weights.
- Do not use ADB taps, swipes, unattended gameplay, or real-money gameplay.
- Do not claim production accuracy or production qualification.

## Required behavior

1. Validate `bot_id`, frame identity, image shape, and source metadata before
   invoking adapters.
2. Use dependency injection protocols for card, button, OCR, and turn adapters;
   tests must use deterministic fakes.
3. Preserve the frame `bot_id`, `frame_id`, and timestamp in the snapshot.
4. Return typed `DetectedCard`, `ButtonState`, OCR metadata, and hybrid
   `TurnOwnerEvidence` through the existing contract boundary.
5. Any adapter exception, invalid output, identity mismatch, or conflicting
   turn signals must return a safe result (`turn_owner=None`, disabled/invisible
   action buttons, and a failed result) without invoking decision/action code.
6. Do not silently drop adapter failures. Return structured failure reasons.
7. Preserve deterministic ordering of cards, buttons, OCR fields, and failures.
8. Do not mutate the input frame or adapter-owned objects.

## Acceptance

- Focused pipeline tests pass.
- Full repository test suite passes.
- Compile, module governance, scope guard, and `git diff --check` pass.
- Tests cover happy path, bot/frame mismatch, malformed adapter output,
  adapter exception, conflicting turn signals, deterministic ordering, and
  no input mutation.
- Evidence must state that this is a wiring candidate only and that production
  dataset/model qualification remains blocked.
