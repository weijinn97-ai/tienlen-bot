# Inference Runner Failure Handling

This document explains the isolation and reporting mechanism for errors encountered during the perception UI inference process.

## Failure Isolation

To prevent component failures (such as a template match crash or OCR exceptions) from crashing the entire replay run, the runner isolates all exceptions on a per-frame, per-component basis.

When a component fails, the runner:
1. Records a structured failure record containing the exact component and failure reason code.
2. Emits a safe-negative fallback prediction for the failed component (e.g., button invisible and disabled, OCR field set to `"UNKNOWN"`, or turn owner set to `None`).
3. Continues execution of subsequent frames normally.

## Failure Reason Codes

- `IMAGE_INTEGRITY_ERROR`: Raised when an image path, size, checksum, or dimensions fail validation.
- `BUTTON_DETECTOR_ERROR`: Raised when `TemplateButtonDetector.detect()` throws an exception.
- `OCR_DETECTOR_ERROR`: Raised when `TesseractOcr.recognize()` throws an exception.
- `TURN_DETECTOR_ERROR`: Raised when `HybridTurnOwnerDetector.detect()` throws an exception.
- `CONSENSUS_ERROR`: Raised when consensus observation throws an exception.

## Exit Status Mapping

At the end of a run, the CLI returns exit codes depending on the failure presence:
- `0 COMPLETE`: Replay completed with zero failure records and at least one processed frame.
- `1 DEGRADED`: Replay completed but logged one or more failure records.
- `2 NO_DATA`: Frame index was empty (processed 0 frames).
- `3 INVALID`: An integrity, validation, path, resource limit, or overlap error occurred prior to runner execution.
