# GEMINI-CONTRACT-01 Final Report

## Task

Stabilize serialization and compatibility fixtures for contracts used across
process boundaries and replay.

## Status: COMPLETE

## Branch + Commit

- Branch: `agent/gemini-contract-01`
- Baseline: `gemini-contract-01-baseline` (`2b1fe57`)
- Commit: pending (see below)

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `contracts/serialization.py` | NEW | Canonical JSON serialization with envelope format for all 10 contract types |
| `contracts/__init__.py` | MODIFIED | Export `CONTRACT_SCHEMA_VERSION`, `contract_to_dict`, `contract_from_dict`, `contract_to_json`, `contract_from_json` |
| `tests/test_contract_serialization.py` | NEW | 51 tests covering round-trip, determinism, fixtures, errors, consumers |
| `tests/fixtures/contracts_v1/perception_snapshot_full.json` | NEW | Full PerceptionSnapshot v1 fixture |
| `tests/fixtures/contracts_v1/table_state_full.json` | NEW | Full TableState v1 fixture |
| `tests/fixtures/contracts_v1/action_plan_play.json` | NEW | ActionPlan PLAY with VerifySpec fixture |
| `tests/fixtures/contracts_v1/action_plan_wait.json` | NEW | ActionPlan WAIT minimal fixture |
| `docs/acceptance/contracts/0.2.0/README.md` | NEW | Acceptance evidence |
| `docs/acceptance/contracts/0.2.0/commands.txt` | NEW | Verification commands |
| `docs/acceptance/contracts/0.2.0/metrics.json` | NEW | Machine-readable metrics |
| `docs/acceptance/contracts/0.2.0/artifacts.sha256` | NEW | SHA-256 checksums |
| `docs/acceptance/contracts/0.2.0/failures.md` | NEW | Known failures/limitations |

## Completed

- [x] `contracts/serialization.py` with public API: `CONTRACT_SCHEMA_VERSION`, `contract_to_dict`, `contract_from_dict`, `contract_to_json`, `contract_from_json`
- [x] Round-trip support for all 10 required types: Rect, DetectedCard, CardCombo, ButtonState, TurnOwnerEvidence, PerceptionSnapshot, TableState, VerifySpec, ActionPlan, ConsensusSpec
- [x] Envelope format with `schema_version`, `contract_type`, `payload`
- [x] Canonical deterministic JSON (sorted keys, compact separators, no NaN/Infinity)
- [x] Enum serialization by `.value`
- [x] Enum-keyed mapping → stable string keys → restored enum
- [x] Tuple restoration from lists
- [x] Strict validation: unknown schema/type, missing/extra fields, invalid values
- [x] No pickle/eval/dynamic import/arbitrary class construction
- [x] 4 v1 compatibility fixtures under `tests/fixtures/contracts_v1/`
- [x] 51 test cases in `tests/test_contract_serialization.py`
- [x] Consumer smoke tests: GameStateAdapter + replay table_state_to_dict/from_dict
- [x] Acceptance evidence bundle under `docs/acceptance/contracts/0.2.0/`
- [x] Export via `contracts/__init__.py`

## Not Completed

Nothing. All task requirements are met.

## Tests Run + Exact Result

```
py -3 -m unittest discover -s tests -v
Ran 161 tests in 3.578s
OK

py -3 -m unittest discover -s tests -p "test_contract_serialization.py" -v
Ran 51 tests in 0.038s
OK

powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
Gemini scope check passed. Task=GEMINI-CONTRACT-01; branch=agent/gemini-contract-01; changed=7

py -3 tools/check_module_governance.py
Module governance checks passed.

py -3 -m compileall -q bot contracts tools
(no output = success)

git diff --check
(no output = clean)
```

## Evidence/Artifact

- `docs/acceptance/contracts/0.2.0/` — full evidence bundle
- `docs/acceptance/contracts/0.2.0/artifacts.sha256` — checksums

## Known Risks

None. No existing tests or behavior were modified.

## Proposed Next Step

Owner reviews PR, runs verification commands from `docs/acceptance/contracts/0.2.0/commands.txt`,
and decides whether to promote `MOD-CONTRACTS` to `0.2.0 CANDIDATE` or `LOCKED`.
