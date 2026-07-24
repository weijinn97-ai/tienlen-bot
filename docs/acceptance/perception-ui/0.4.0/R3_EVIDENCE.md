# GEMINI-PERCEPTION-UI-01B R3 Evidence

## Identity

- Baseline tag: `gemini-perception-ui-01b-baseline`
- Baseline commit: `9123abaecd59b001ff679fefcb1fcfc2490dbb71`
- Working branch: `agent/gemini-perception-ui-01b`
- Implementation commit: `a092aff54228651feb7efbfdba1a3a85bdace38c`
- Evidence correction: this follow-up evidence-only commit

## Changed files and line counts

| File | Lines |
|---|---:|
| `bot/perception/ui_inference_runner.py` | 1546 |
| `bot/perception/__init__.py` | 113 |
| `tools/run_perception_ui_replay.py` | 179 |
| `tests/test_perception_ui_inference_runner.py` | 1739 |

## Safety repairs

1. Button output honors `ButtonState.is_visible` and always disables invisible buttons.
2. The first frame never invokes the turn detector and cannot emit an owner. Positive turn output requires valid hybrid evidence, agreeing signals, `required_matches == 3`, observed `4`, matching at least `3`, and the latest detection matching the owner.
3. Configuration is loaded before source ingestion. All six resource limits are exact positive integers constrained by hard ceilings.
4. OCR output ROI and nested highlight/card-delta evidence are type, bounds, and consistency checked.
5. CLI exit codes 0, 1, 2, and 3 are exercised through real subprocesses without importing `tests.*`.
6. Output is staged atomically and checked against the configured total output limit.

## Verification results

| Gate | Result |
|---|---|
| Focused runner tests | `72/72 OK` |
| Full test suite | `299/299 OK` |
| Python compileall | PASS |
| Module governance | PASS |
| Scope guard | PASS |
| Baseline diff-check | PASS |
| Acceptance artifact checksums | PASS |

## Two-run deterministic hashes

Both runs used the same source bundle, config, injected adapters, and clock value `1.0`.

| Artifact | Run 1 SHA-256 | Run 2 SHA-256 | Match |
|---|---|---|---|
| `predictions.jsonl` | `f19653d1ff9cd587c80598eb7e9d67ae31c33923e54a18cdedf6b42a6372addb` | `f19653d1ff9cd587c80598eb7e9d67ae31c33923e54a18cdedf6b42a6372addb` | True |
| `failures.jsonl` | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` | True |
| `inference_manifest.json` | `aa84216faafa7f34c8ebaf21c35ebcb0d2e35ba2645b3f23b6c4e72c2c6dee5b` | `aa84216faafa7f34c8ebaf21c35ebcb0d2e35ba2645b3f23b6c4e72c2c6dee5b` | True |

`run_metadata.json` is intentionally excluded because it contains runtime metadata.

## Input immutability hashes

The following consumed inputs were hashed before and after the two runs. Every before/after pair matched exactly.

| Input | Before SHA-256 | After SHA-256 |
|---|---|---|
| `source.json` | `4a130eaf884a0ce35abf7a1c0d4e067b9c802ff58332b068ecb7af61e5c10605` | `4a130eaf884a0ce35abf7a1c0d4e067b9c802ff58332b068ecb7af61e5c10605` |
| `frame_index.jsonl` | `55511ceb74b20f21f39fbbdd232580a1445dec21f1bb7081d77f488d801da806` | `55511ceb74b20f21f39fbbdd232580a1445dec21f1bb7081d77f488d801da806` |
| `config.json` | `2a87de462a91add611aae9573b7e5ed909e0e3624f1cddcd5880f40104f178c8` | `2a87de462a91add611aae9573b7e5ed909e0e3624f1cddcd5880f40104f178c8` |
| `templates/play_enabled.png` | `6650192189762f257d44c31118831d333bf970be8e83bb4a8d031b966354c38c` | `6650192189762f257d44c31118831d333bf970be8e83bb4a8d031b966354c38c` |
| `frames/f1.png` | `d18b6ed038c377e1b60de4ae5065fe2f67e0bbedccb9b74d25385d7aabd6930e` | `d18b6ed038c377e1b60de4ae5065fe2f67e0bbedccb9b74d25385d7aabd6930e` |

## Negative claims

No live ADB operation, gameplay action, model training, dependency change, network request, merge, or production readiness claim was made. Production qualification remains blocked pending owner-approved real replay/data evidence.
