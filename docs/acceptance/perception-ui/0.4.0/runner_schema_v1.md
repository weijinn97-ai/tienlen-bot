# Runner Schema Version 1

This document specifies the exact JSON schemas for the output files produced by the perception UI inference runner version 1.

## predictions.jsonl

Each line is a single JSON object with sorted keys representing the predictions for one frame:

```json
{
  "frame_id": "session-01-000001",
  "buttons": {
    "play": {"visible": false, "enabled": false, "confidence": 0.0},
    "pass": {"visible": false, "enabled": false, "confidence": 0.0}
  },
  "ocr_fields": [
    {"field_id": "self_count", "text": "UNKNOWN", "confidence": 0.0}
  ],
  "turn_owner": null,
  "turn_observed_frames": 1,
  "turn_matching_frames": 0,
  "turn_latest_frame_matches": false,
  "latency_ms": 0.0,
  "source_commit": "<40 hex lowercase source commit>",
  "config_sha256": "<64 hex lowercase config hash>"
}
```

## failures.jsonl

Each line is a single JSON object with sorted keys representing a structured component failure:

```json
{
  "frame_id": "session-01-000001",
  "reason_code": "IMAGE_LOAD_ERROR",
  "details": "Failed to decode frame image bytes"
}
```
