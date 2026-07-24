# GEMINI-PERCEPTION-UI-01B

## 1. Muc tieu duy nhat

Xay read-only inference runner deterministic de doc frame tu source manifest,
goi detector UI hien huu qua typed adapter, va ghi `predictions.jsonl` dung schema
evaluator 01A.

Task nay KHONG calibration, KHONG train, KHONG action, KHONG ADB tap va KHONG
chung minh production metric. Ket qua dung la runner an toan co the dua vao
locked replay sau nay ma khong thay evaluator hay detector da nghiem thu.

## 2. Setup bat buoc

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git tienlen-bot-gemini
cd tienlen-bot-gemini
git checkout gemini-perception-ui-01b-baseline
git switch -c agent/gemini-perception-ui-01b
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
```

Baseline expected: `227/227` tests pass. Neu count hoac gate khac, dung va tao
`GEMINI_PERCEPTION_UI_01B_OUTPUT/BLOCKERS.md`. Khong sua test cu.

## 3. Scope deny-by-default

Duoc tao moi:

- `bot/perception/ui_inference_runner.py`
- `tools/run_perception_ui_replay.py`
- `tests/test_perception_ui_inference_runner.py`
- `tests/fixtures/perception_ui_runner/**`
- `docs/acceptance/perception-ui/0.4.0/**`
- `GEMINI_PERCEPTION_UI_01B_OUTPUT/**`

Chi duoc sua `bot/perception/__init__.py` de export public runner API.

Cam sua evaluator/evidence 01A, detector hien huu, contracts, serialization,
action, state, runtime, replay, capture, rules, test/fixture cu, raw dataset,
template cu, weights, dependency, CI, guard, registry va active task.

Cam ADB tap/click/swipe, unattended gameplay, network/model download, train,
force push, merge, commit main, doc ground truth trong inference va claim
production/CANDIDATE/LOCKED. Neu can path bi cam, ghi blocker; khong workaround.

## 4. Kien truc bat buoc

`ui_inference_runner.py` la orchestration read-only. Import module khong khoi tao
Tesseract, model, ADB, MEmu, network hoac doc file.

Public API toi thieu:

```python
load_ui_inference_source(source_dir) -> UiInferenceSource
load_ui_inference_config(config_path) -> UiInferenceConfig
run_ui_inference(source, adapters, config, clock=...) -> UiInferenceResult
write_ui_inference_result(result, output_dir) -> None
```

Phai co immutable dataclass/Protocol cho source, frame, button adapter, OCR
adapter, card-count provider, hybrid turn adapter, config, prediction, structured
failure va result. Khong `Any` tai public boundary khi co the type ro. Khong
pickle, `eval`, `exec`, dynamic import, arbitrary class construction hay global
mutable state.

Adapter mac dinh chi boc API hien huu, khong copy/sua algorithm:

- `TemplateButtonDetector.detect(frame)`;
- `TesseractOcr.recognize(frame, roi, whitelist=...)`;
- `HybridTurnOwnerDetector.detect(...)`;
- `HybridTurnOwnerConsensus(history_size=4, required_matches=3)`.

Dependency khoi tao lazy trong CLI/factory. Test dung fake adapter, khong yeu cau
Tesseract executable, GPU, ADB hoac network.

## 5. Source manifest v1 va anti-leakage

Input:

```text
source/
  source.json
  frame_index.jsonl
  frames/...
config.json
```

`source.json` exact schema:

```json
{
  "schema_version": 1,
  "dataset_id": "ui-source-v1",
  "viewport": {"width": 1280, "height": 720},
  "frame_index": "frame_index.jsonl",
  "frame_index_sha256": "<64 lowercase hex>"
}
```

Frame record exact schema:

```json
{
  "frame_id": "session-01-000001",
  "relative_path": "frames/session-01-000001.png",
  "sha256": "<64 lowercase hex>",
  "session_id": "session-01",
  "sequence_id": "turn-0001",
  "frame_index": 1,
  "capture_ts_ms": 1000,
  "player_card_counts": {
    "SELF": 13,
    "LEFT": 13,
    "TOP": 13,
    "RIGHT": 13
  }
}
```

Integrity:

- exact keys/type; bool khong la int/float;
- reject duplicate JSON key, NaN/Infinity, blank JSONL, invalid UTF-8;
- ID ASCII an toan; ID/path unique;
- path relative POSIX; reject absolute, UNC, drive, `..`, backslash;
- `Path.resolve(strict=True)` va canonical containment;
- reject symlink/reparse escape, path/case collision, duplicate image SHA;
- verify checksum source/index/image truoc detector;
- image PNG/JPEG valid, non-empty, exact viewport;
- file count/byte/pixel guard;
- index va timestamp tang nghiem ngat trong `(session_id, sequence_id)`;
- sequence khong interleave; reset state tai boundary;
- card count exact int `[0,13]` cho du bon seat.

Runner chi nhan source khong co label. Neu source/config co key/path
`ground_truth`, `expected_*`, `label` hoac `reviewer`, phai reject. Test phai
chung minh runner khong mo `ground_truth.jsonl` ke ca file ton tai canh source.

## 6. Config strict va immutable

Config phai co schema version, OCR normalized ROI/whitelist, OCR minimum
confidence mac dinh `0.75`, button template directory va checksum tung template,
turn consensus exact `4/3`, resource limits va `source_commit` 40 lowercase hex.

Reject missing/extra key, duplicate field/ROI, unknown OCR field, ROI out of
frame, threshold ngoai `[0,1]`, non-finite, mixed viewport, unknown enum va path
escape. Nested collection immutable bang `tuple`, `MappingProxyType` hoac
equivalent.

Tinh `config_sha256` tu canonical JSON UTF-8/LF, sorted key, no NaN. Khong nhan
hash do caller khai. Moi prediction dung cung config hash va source commit.

## 7. Suy luan fail-safe

Moi frame sinh dung mot prediction theo thu tu source va schema 01A:

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
  "source_commit": "<40 hex>",
  "config_sha256": "<64 hex>"
}
```

Button:

- map exact `ButtonId.PLAY` va `ButtonId.PASS`;
- missing -> invisible, disabled, confidence 0;
- duplicate -> confidence cao nhat, tie-break deterministic;
- invisible bat buoc disabled;
- invalid confidence/type/ROI -> safe frame failure;
- khong sua confidence de dat gate.

OCR:

- chi field config va dung thu tu config;
- confidence < threshold -> exact `UNKNOWN`;
- exception/empty/invalid -> `UNKNOWN`, confidence 0;
- khong trim, case-fold hoac hieu chinh text sau adapter.

Turn:

- secondary signal chi la delta card count frame truoc/current;
- frame dau sequence -> owner null;
- owner chi khi highlight va expected-next tu delta khop;
- consensus exact 3/4 va latest frame nam trong nhom dong thuan;
- reset tai sequence/session boundary va sau integrity failure;
- conflict, exception, stale/gap -> null;
- khong carry history giua sequence/session.

Failure:

- source/config/integrity error abort truoc detector, khong partial output;
- detector error emit safe-negative prediction va structured failure;
- khong chac thi khong emit PLAY enabled, OCR text hoac SELF turn;
- stable reason code/frame/component; khong absolute path, secret, stack trace
  hay nondeterministic exception text.

## 8. Deterministic output va CLI

Latency dung injectable monotonic clock, reject regression/non-finite, round 6
decimal. Test dung fake clock.

Output:

```text
predictions.jsonl
failures.jsonl
inference_manifest.json
run_metadata.json
```

Ba artifact dau byte deterministic; sorted compact JSON, UTF-8 no BOM, LF-only,
no NaN. Atomic temp+replace, cleanup temp, output ngoai source/config, khong
overwrite input. Manifest ghi SHA-256 source/config/output. Timestamp, hostname,
absolute path chi trong nondeterministic `run_metadata.json`.

CLI:

```powershell
py -3 tools/run_perception_ui_replay.py `
  --source <source-dir> `
  --config <config.json> `
  --output <output-dir>
```

Exit: `0 COMPLETE`, `1 DEGRADED`, `2 NO_DATA`, `3 INVALID`. Khong stack trace cho
data error; khong in PASS hay production-ready.

## 9. Test bat buoc

Chi tao `tests/test_perception_ui_inference_runner.py`, toi thieu 40 test:

1. happy path goi moi adapter dung mot lan/frame;
2. prediction evaluator 01A parse duoc;
3. khong doc ground truth;
4. khong mutate frame/input;
5. deterministic two-run checksum;
6. exact/duplicate/missing/extra JSON key;
7. blank JSONL, UTF-8, NaN/Infinity;
8. bool-as-number rejection;
9. traversal/absolute/UNC/drive/backslash;
10. symlink/reparse escape;
11. path/case collision;
12. missing/corrupt/checksum/dimension image;
13. duplicate frame ID/path/image hash;
14. index gap/duplicate/order/interleave;
15. timestamp duplicate/regression;
16. invalid/missing card count;
17. resource limit guard;
18. forbidden ground-truth-like key;
19. lazy import/no side effect;
20. button missing safe state;
21. duplicate button deterministic;
22. invisible cannot enabled;
23. invalid button output safe failure;
24. OCR low confidence UNKNOWN;
25. OCR error/empty/invalid UNKNOWN;
26. OCR exact text not normalized;
27. turn disagreement null;
28. first sequence frame null;
29. 3/4 consensus includes latest;
30. reset sequence/session;
31. detector exception isolation;
32. no false positive after component failure;
33. clock regression/non-finite;
34. atomic cleanup;
35. input/output overlap;
36. exit code 0/1/2/3;
37. no Tesseract/GPU/ADB/network in tests;
38. immutable dataclasses/nested mapping;
39. source/config hash consistency;
40. one-to-one stable prediction order.

Khong sua evaluator/test 01A. Khong tao hang nghin image.

## 10. Evidence va Definition of Done

Tao `docs/acceptance/perception-ui/0.4.0/` gom `README.md`, `commands.txt`,
`failures.md`, `runner_schema_v1.md`, `sample_inference_manifest.json` va
`artifacts.sha256`.

Done khi baseline 227 van pass; co >=40 focused test moi; full suite, scope,
governance, compile va diff-check pass; output evaluator-compatible; adversarial
failure explicit; deterministic checksum match; input unchanged; zero
ADB/action/network/train; module van `IN_PROGRESS`; Draft PR `Relates to #8`.

Evidence phai ghi production gate van BLOCKED vi chua co owner-approved locked
replay 2.000 negative, OCR ground truth va turn transition replay.

## 11. Verification va delivery

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -p "test_perception_ui_inference_runner.py" -v
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
git diff --check
git status --short
git diff --name-status gemini-perception-ui-01b-baseline...HEAD
```

Dung hai commit:

```text
Implement read-only perception UI inference runner
Add reproducible perception UI runner evidence
```

Commit 1 chi code/test; commit 2 chi evidence/report. Push
`agent/gemini-perception-ui-01b`, mo Draft PR, `Relates to #8`, khong merge.

Final report tai `GEMINI_PERCEPTION_UI_01B_OUTPUT/FINAL_REPORT.md`, ghi baseline,
branch, hai SHA, changed files/line counts, test totals, command/exit code,
two-run hashes, input unchanged, adapter da goi, blockers, va xac nhan no ADB,
no action, no train, no merge. Sau do dung, khong tu bat dau 01C.
