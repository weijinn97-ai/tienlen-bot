# GEMINI-CONTRACT-01 Final Report (Repair PR #26)

## Task

Stabilize serialization, strict wire-boundary validation, and compatibility
fixtures for contracts used across process boundaries and replay.

## Status: REPAIRED & COMPLETE

## Branch + Commit

- Branch: `agent/gemini-contract-01`
- Baseline: `gemini-contract-01-baseline` (`2b1fe57`)

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `contracts/serialization.py` | MODIFIED | Canonical JSON serialization with strict wire-boundary validation for all 10 contract types |
| `contracts/__init__.py` | MODIFIED | Export `CONTRACT_SCHEMA_VERSION`, `contract_to_dict`, `contract_from_dict`, `contract_to_json`, `contract_from_json` |
| `tests/test_contract_serialization.py` | MODIFIED | 60 tests covering round-trip, determinism, fixtures, strict wire validation, error handling, consumers |
| `tests/fixtures/contracts_v1/perception_snapshot_full.json` | NEW | Full PerceptionSnapshot v1 fixture |
| `tests/fixtures/contracts_v1/table_state_full.json` | NEW | Full TableState v1 fixture |
| `tests/fixtures/contracts_v1/action_plan_play.json` | NEW | ActionPlan PLAY with VerifySpec fixture |
| `tests/fixtures/contracts_v1/action_plan_wait.json` | NEW | ActionPlan WAIT minimal fixture |
| `docs/acceptance/contracts/0.2.0/README.md` | MODIFIED | Acceptance evidence |
| `docs/acceptance/contracts/0.2.0/commands.txt` | MODIFIED | Verification commands and LF SHA-256 calculation method |
| `docs/acceptance/contracts/0.2.0/metrics.json` | MODIFIED | Machine-readable metrics (170 tests total) |
| `docs/acceptance/contracts/0.2.0/artifacts.sha256` | MODIFIED | LF-normalized SHA-256 checksums |
| `docs/acceptance/contracts/0.2.0/failures.md` | MODIFIED | Strict wire validation behavior & risk documentation |

## Completed Repair Requirements (Repair Spec Sections 1-6)

- [x] **Safe Setup**: Checked status, fetched origin, verified clean worktree and baseline tests (110 pass)
- [x] **Scope Restriction**: Modified only whitelisted files (`contracts/serialization.py`, `contracts/__init__.py`, `tests/test_contract_serialization.py`, `docs/acceptance/contracts/0.2.0/**`, `GEMINI_CONTRACT_01_OUTPUT/**`)
- [x] **Strict Wire-Boundary Validation**:
  - `parse_constant` callback in `contract_from_json` rejects JSON `NaN`, `Infinity`, `-Infinity`
  - Rejects direct-dict `float("nan")`, `float("inf")`, `float("-inf")` in confidence fields
  - Requires `type(schema_version) is int` (rejects `schema_version=True`)
  - Validates `player_card_counts`: dict container, exact keys `"0"`, `"1"`, `"2"`, `"3"` (rejects `"00"`, `"4"`), count `type(count) is int` (rejects `True`), `0 <= count <= 13`, rejects duplicate normalized keys
  - `ButtonState.button_id` requires string; `ActionPlan.target_button` requires string or `None` (rejects dict/list/number/bool)
  - Exact wire types: integer fields require `type(val) is int` (rejects `bool`), booleans require `type(val) is bool`, lists require `type(val) is list`, dicts require `type(val) is dict`
- [x] **Mandatory Regression Tests**: Added 9 new test cases in `StrictWireValidationTests` (60 total serialization tests, 170 total repository tests)
- [x] **Evidence & Checksums**: Updated all evidence files, metrics (170 tests), and LF-normalized SHA-256 checksums
- [x] **Verification & Delivery**: Passed all checks (`unittest`, `compileall`, `check_module_governance.py`, `guard_scope.ps1`, `git diff --check`, `git diff --name-only`)

## Tests Run + Exact Result

```
py -3 -m unittest discover -s tests -p "test_contract_serialization.py" -v
Ran 60 tests in 0.019s
OK

py -3 -m unittest discover -s tests -v
Ran 170 tests in 3.320s
OK

powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
Gemini scope check passed. Task=GEMINI-CONTRACT-01; branch=agent/gemini-contract-01; changed=13

py -3 tools/check_module_governance.py
Module governance checks passed.

py -3 -m compileall -q bot contracts tools
(no output = success)

git diff --check
(no output = clean)
```

## Proposed Next Step

Owner reviews PR #26 update and decides on promoting `MOD-CONTRACTS` to `0.2.0 CANDIDATE` or `LOCKED`.
