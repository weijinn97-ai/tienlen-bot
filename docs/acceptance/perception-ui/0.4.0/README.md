# Acceptance Review: Perception UI Inference Runner 0.4.0

This package contains the acceptance review evidence for the read-only perception UI inference runner (`ui_inference_runner.py`) and CLI script (`run_perception_ui_replay.py`).

## Acceptance Status

- **Status**: REVIEW_REQUIRED
- **Production Replay Gate**: **BLOCKED**
  - Reason: The repository currently lacks the owner-approved locked replay of 2,000 negative frames, OCR ground truth annotations, and turn transition replay history necessary for full end-to-end production verification.

## Deliverables

- `bot/perception/ui_inference_runner.py`: Read-only orchestration module.
- `tools/run_perception_ui_replay.py`: Command line tool.
- `tests/test_perception_ui_inference_runner.py`: 72 focused unit, adversarial, and subprocess tests.

## Evidence Checklist

- `commands.txt`: Shell verification commands.
- `failures.md`: Component failure mapping and exit code documentation.
- `runner_schema_v1.md`: JSON schema specifications.
- `sample_inference_manifest.json`: Structured manifest output sample.
- `R3_EVIDENCE.md`: Exact R3 implementation and verification record.
