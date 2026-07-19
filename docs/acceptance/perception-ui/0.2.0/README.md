# Perception UI 0.2.0 Evidence

Status: `IN_PROGRESS`, not `CANDIDATE` and not `LOCKED`.

Implemented in this increment:

- OCR returns confidence and fail-safe `UNKNOWN` below threshold.
- Default Tesseract adapter reads per-token confidence.
- Hybrid turn owner still requires highlight and card-count delta agreement.
- Critical turn consensus requires 3 of 4 frames and the latest frame must agree.
- Consensus history is isolated by `bot_id`.

The committed live set is too small for the production gate. Current evidence proves behavior and regression safety only; it does not prove the required production accuracy.
