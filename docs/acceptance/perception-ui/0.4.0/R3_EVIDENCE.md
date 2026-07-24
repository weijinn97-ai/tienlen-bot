# GEMINI-PERCEPTION-UI-01B R3 Evidence

## Identity

- Baseline tag: `gemini-perception-ui-01b-baseline`
- Baseline commit: `9123abaecd59b001ff679fefcb1fcfc2490dbb71`
- Working branch: `agent/gemini-perception-ui-01b`
- Implementation commit: `a092aff`
- Evidence commit: the commit containing this file

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

## Negative claims

No live ADB operation, gameplay action, model training, dependency change, network request, merge, or production readiness claim was made. Production qualification remains blocked pending owner-approved real replay/data evidence.
