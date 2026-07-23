# UiEvaluationBundle Schema Version 1

## Overview
This document specifies the strict, deterministic data format required for evaluating the Perception UI module. A bundle consists of a top-level `bundle.json` manifest, three required JSONL data files, and raw frame image files.

## Directory Structure
```
bundle_dir/
  bundle.json
  <files as referenced in bundle.json>
  frames/
    <image_files>.png
```
Note: Paths must not contain parent references (`..`), absolute paths, UNC paths, or symlink escapes. Aliasing multiple paths to the same canonical file is strictly forbidden.

## bundle.json
A strict JSON object containing:
- `schema_version` (int): Must be 1.
- `dataset_id` (string): Alpha-numeric ID.
- `locked` (boolean): Must be `true` for a `PASS` evaluation status.
- `viewport` (object): Map with `width` (int) and `height` (int) describing the exact dimensions of all frames.
- `files` (object): Map containing relative paths to the required datasets: `frame_index`, `ground_truth`, and `predictions`.
- `sha256` (object): Map containing the exact SHA-256 checksums of the files listed in `files`. Keys must correspond 1:1 with the values in `files`.

## Data Files (JSONL)
All JSONL files must strictly adhere to duplicate key rejection, avoid `NaN`/`Infinity` constants, and avoid booleans where ints/floats are expected. No file can exceed 500,000 lines.

### frame_index
Defines the test set frames.
- `frame_id`: Unique identifier string.
- `relative_path`: Relative path to the raw frame image.
- `sha256`: Expected SHA-256 hash of the frame image bytes.
- `session_id`, `sequence_id`: Sequence identification strings.
- `frame_index`: Strictly monotonically increasing 0-based integer within a sequence.
- `split`: Must be `train`, `val`, or `test`. Test frames must have `review_status` as `APPROVED`.
- `review_status`: Review state.
- `reviewer_id`: Identifier for the reviewer.

### ground_truth
Defines the expected outputs.
- `frame_id`: Identifier string matching `frame_index`.
- `buttons`: Map containing `play` and `pass` objects. Each has `visible` (bool) and `enabled` (bool).
- `ocr_fields`: Array of objects. Each has `field_id` (string), `expected_text` (string), and `critical` (bool).
- `expected_turn_owner`: `SELF`, `LEFT`, `RIGHT`, `TOP`, or `null`.
- `critical_transition`: (bool) Indicates if this frame is a critical game transition.
- `negative_play_frame`: (bool) Indicates a frame where the play button should definitely be disabled/invisible.

### predictions
Defines the model outputs.
- `frame_id`: Identifier string matching `frame_index`.
- `buttons`: Map of `play` and `pass`. Each has `visible`, `enabled`, and `confidence` (float [0,1]).
- `ocr_fields`: Array of objects. Each has `field_id` (string), `text` (string), and `confidence` (float [0,1]).
- `turn_owner`: `SELF`, `LEFT`, `RIGHT`, `TOP`, or `null`.
- `turn_observed_frames`, `turn_matching_frames`: Integers describing sequence-based consensus logic.
- `turn_latest_frame_matches`: (bool) Indicates if the latest frame agrees with the owner.
- `latency_ms`: Execution time (float [0, 60000]).
- `source_commit`: Exact 40-character SHA-1 of the predicting code.
- `config_sha256`: Exact 64-character SHA-256 of the configuration used for inference.

## Validations
- **Images**: Verified byte-for-byte against their checksums and strictly verified to match `viewport` (must be valid PNG/JPEG).
- **Paths**: Canonical path enforcement and absolute/symlink escape rejection.
- **Data Integrity**: Enforced immutability via `tuple` and `MappingProxyType` during execution.
