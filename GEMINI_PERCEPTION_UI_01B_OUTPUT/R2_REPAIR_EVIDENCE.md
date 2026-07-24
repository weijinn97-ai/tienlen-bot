# GEMINI-PERCEPTION-UI-01B — R2 Repair Evidence Report

## Baseline
- Tag: `gemini-perception-ui-01b-baseline`
- Baseline commit: `gemini-perception-ui-01b-baseline` (tag pointing to `f56619b`)

## Implementation Repair Commit
- SHA: `f12c3ec`
- Subject: `Repair perception UI inference runner audit findings`

## Changed Files and Exact Line Counts (LF-canonical)

| File | SHA-256 (first 32 hex) | Lines |
|------|----------------------|-------|
| `bot/perception/ui_inference_runner.py` | `66cb4ad84b4702172787de55d5d1f7b8...` | 1403 |
| `bot/perception/__init__.py` | `1238b5eeb29621618303e9b19c90f454...` | 113 |
| `tests/test_perception_ui_inference_runner.py` | `011fca6ce4ae80e6d3c44f5afce7780a...` | 1457 |
| `tools/run_perception_ui_replay.py` | `92eb62e567686a12ea65618d976acf2e...` | 181 |

## Focused Tests
- Command: `py -3 -m unittest discover -s tests -p "test_perception_ui_inference_runner.py"`
- Result: **Ran 61 tests in ~2.4s — OK**

## Full Suite
- Command: `py -3 -m unittest discover -s tests`
- Result: **Ran 288 tests in ~9s — OK**

## CLI 0/1/2/3 Evidence

| Exit Code | Trigger | STATUS marker |
|-----------|---------|--------------|
| 0 COMPLETE | Valid run, no failures | `STATUS=COMPLETE` |
| 1 DEGRADED | `status_to_exit_code(3, 10)` → 1 | `STATUS=DEGRADED` |
| 2 NO_DATA | `status_to_exit_code(0, 0)` → 2 | `STATUS=NO_DATA` |
| 3 INVALID | Missing source / output overlap | `STATUS=INVALID` |

## Scope / Governance / Compile / Diff Gates

| Gate | Command | Result |
|------|---------|--------|
| Scope | `powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1` | PASS — `Gemini scope check passed. Task=GEMINI-PERCEPTION-UI-01B; branch=agent/gemini-perception-ui-01b; changed=11` |
| Compile | `py -3 -m compileall -q bot contracts tools` | Exit 0, no output |
| Governance | `py -3 tools/check_module_governance.py` | `Module governance checks passed.` |
| Diff check | `git diff --check gemini-perception-ui-01b-baseline...HEAD` | Exit 0, no output |

## Two-Run Deterministic Hashes

| Artifact | Run 1 (first 16 hex) | Run 2 (first 16 hex) | match |
|----------|---------------------|---------------------|-------|
| `predictions.jsonl` | `d64b7aea5e4d2110...` | `d64b7aea5e4d2110...` | **True** |
| `failures.jsonl` | `01ba4719c80b6fe9...` | `01ba4719c80b6fe9...` | **True** |
| `inference_manifest.json` | `1364ee2373ab0f47...` | `1364ee2373ab0f47...` | **True** |

`run_metadata.json` is explicitly nondeterministic and excluded from deterministic comparison.

## Input Immutability Hashes

Source files verified byte-for-byte unchanged after inference run (sha256 computed from LF-canonical content):

- `bot/perception/ui_inference_runner.py`: `66cb4ad84b4702172787de55d5d1f7b8...`
- `tests/test_perception_ui_inference_runner.py`: `011fca6ce4ae80e6d3c44f5afce7780a...`

## Acceptance Evidence Checksums (LF-canonical, UTF-8 no BOM)

| File | SHA-256 |
|------|---------|
| `docs/acceptance/perception-ui/0.4.0/README.md` | `89f5d6f05036f3ae7a7b44bb4c85b321b742ad70302d46ba3cc9569b2879c0f7` |
| `docs/acceptance/perception-ui/0.4.0/artifacts.sha256` | `d304834722ebd464b1f1c0796a636adc3f162c5f0e339d44b78ba48bb34da1f9` |
| `docs/acceptance/perception-ui/0.4.0/commands.txt` | `47e81246d59a1ffb0e04d16de76864ff27ee72d33108eb83f36999066b43fd96` |
| `docs/acceptance/perception-ui/0.4.0/failures.md` | `9a09e5be6d83cbfea8cf7af0cbb730407ae59231f8c814532b965504a751ee4c` |
| `docs/acceptance/perception-ui/0.4.0/runner_schema_v1.md` | `2079da60b61ba66d24a0258f677b891d43b016ee7e85a2699feb839759b7a5c3` |
| `docs/acceptance/perception-ui/0.4.0/sample_inference_manifest.json` | `acafb3d3dcc8a51f4cd358e804f1b936506ac2e922ec68aec212a1177a939c06` |

## Production Blockers

- `MOD-PERCEPTION=IN_PROGRESS`
- Production qualification **BLOCKED** pending owner acceptance of this PR.
- No Tesseract integration test available in CI (injectable adapter pattern used for test isolation).

## Prohibited Operations Confirmation

- No ADB actions performed
- No gameplay actions performed
- No training performed
- No dependency changes (no Pillow, no new packages)
- No merge performed
- No 01C started
- No force-push, rebase, amend, reset, or rewrite of existing commits
- No new branch or PR created
- No modification to the baseline tag
