# GEMINI-PERCEPTION-UI-01A

## 1. Muc tieu

Xay evaluator locked-replay deterministic cho button, OCR va hybrid turn-owner
truoc khi calibration detector hoac chay live action. Task nay tao cach do metric
that va fail-safe; khong duoc sua detector hien huu va khong duoc tu claim
production-ready.

Ly do tach 01A:

- dataset hien tai chi co 36 anh `MY_HAND`;
- 36/36 anh thieu bbox production;
- khong co val/test doc lap;
- khong co `TABLE_PLAY`;
- chi co 3 frame button transition, thieu toi thieu 2.000 negative/disabled;
- khong co locked OCR ground truth va locked turn-transition replay.

Neu khong co evaluator va bundle contract khoa truoc, moi metric calibration/train
deu khong the tai lap va rat de bi leakage.

## 2. Setup bat buoc

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git tienlen-bot-gemini
cd tienlen-bot-gemini
git checkout gemini-perception-ui-01a-baseline
git switch -c agent/gemini-perception-ui-01a
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
```

Baseline phai co dung `182/182` test pass. Neu khac, dung va tao
`GEMINI_PERCEPTION_UI_01A_OUTPUT/BLOCKERS.md`. Khong sua test cu de lam baseline pass.

## 3. Scope deny-by-default

Duoc tao moi:

- `bot/perception/ui_evaluation.py`
- `tools/evaluate_perception_ui.py`
- `tests/test_perception_ui_evaluation.py`
- `tests/fixtures/perception_ui/**`
- `docs/acceptance/perception-ui/0.3.0/**`
- `GEMINI_PERCEPTION_UI_01A_OUTPUT/**`

Chi duoc sua file hien huu:

- `bot/perception/__init__.py` de export public evaluator API

Cam:

- sua `buttons.py`, `ocr.py`, `turn_owner.py`, `yolo_cards.py`, `fan_cards.py`;
- sua contracts/serialization, rules, state, action, runtime, replay hoac capture;
- sua test/fixture cu;
- ghi/xoa/doi ten raw data;
- train model, cai dependency, commit weight;
- sua module registry, active task, guard hoac CI;
- chay ADB tap, gameplay unattended hoac live action;
- ghi metric production khi bundle chua locked/du coverage.

Neu implementation can mot path cam, dung va ghi `BLOCKERS.md`; khong mo rong scope.

## 4. Kien truc bat buoc

Tao module pure/deterministic `bot/perception/ui_evaluation.py`. Module khong
duoc khoi tao Tesseract, model, ADB, MEmu hoac network khi import.

Public API toi thieu, ten co the dieu chinh neu ro rang va nhat quan:

```python
load_ui_evaluation_bundle(bundle_dir) -> UiEvaluationBundle
evaluate_ui_predictions(bundle, config=...) -> UiEvaluationResult
write_ui_evaluation_result(result, output_dir) -> None
```

Export cac type/API chinh qua `bot/perception/__init__.py`.

Phai dung immutable dataclass hoac typed structure cho:

- bundle metadata;
- frame index;
- expected button state;
- expected OCR field;
- expected turn state;
- prediction record;
- metric/gate result;
- structured failure.

Khong dung pickle, eval, dynamic import hoac arbitrary class construction.

## 5. Locked bundle format v1

Mot bundle toi thieu:

```text
bundle/
  bundle.json
  frame_index.jsonl
  ground_truth.jsonl
  predictions.jsonl
  frames/...
```

### `bundle.json`

Bat buoc co:

```json
{
  "schema_version": 1,
  "dataset_id": "ui-locked-v1",
  "locked": true,
  "viewport": {"width": 1280, "height": 720},
  "files": {
    "frame_index": "frame_index.jsonl",
    "ground_truth": "ground_truth.jsonl",
    "predictions": "predictions.jsonl"
  },
  "sha256": {
    "frame_index.jsonl": "<64 hex>",
    "ground_truth.jsonl": "<64 hex>",
    "predictions.jsonl": "<64 hex>"
  }
}
```

Quy tac:

- exact keys; missing/extra field fail;
- `schema_version` exact int, bool khong duoc coi la int;
- JSON duplicate key, NaN/Infinity, wrong type fail ro reason;
- `locked=false` duoc parse nhung ket qua gate bat buoc `INSUFFICIENT_DATA`;
- path phai relative, nam trong bundle, khong `..`, khong absolute, khong symlink escape;
- checksum mismatch fail truoc evaluation;
- file JSONL UTF-8, moi dong mot object, duplicate ID fail;
- khong silently default hoac bo field.

### `frame_index.jsonl`

Moi record:

```json
{
  "frame_id": "session-01-000001",
  "relative_path": "frames/session-01-000001.png",
  "sha256": "<64 hex>",
  "session_id": "session-01",
  "sequence_id": "turn-0001",
  "frame_index": 1,
  "split": "test",
  "review_status": "APPROVED",
  "reviewer_id": "reviewer-02"
}
```

Bat buoc:

- `frame_id` unique;
- image SHA-256 unique trong split `test`; khong duoc nhan ban cung mot anh de tang coverage;
- sequence frame index tang nghiem ngat;
- split chi `train|val|test`, evaluation gate chi dung `test`;
- `review_status` phai `APPROVED` cho moi test record;
- reviewer_id khong rong;
- image checksum/dimension khop viewport;
- corrupt/missing image fail bundle validation.

### `ground_truth.jsonl`

Moi frame co exact fields:

```json
{
  "frame_id": "session-01-000001",
  "buttons": {
    "play": {"visible": true, "enabled": false},
    "pass": {"visible": true, "enabled": true}
  },
  "ocr_fields": [
    {"field_id": "self_count", "expected_text": "13", "critical": true}
  ],
  "expected_turn_owner": null,
  "critical_transition": false,
  "negative_play_frame": true
}
```

Button gate toi thieu danh gia `play` va `pass`. `negative_play_frame=true` nghia
prediction `play.visible=true && play.enabled=true` la safety failure.

### `predictions.jsonl`

Moi frame co exact fields:

```json
{
  "frame_id": "session-01-000001",
  "buttons": {
    "play": {"visible": true, "enabled": false, "confidence": 0.98},
    "pass": {"visible": true, "enabled": true, "confidence": 0.99}
  },
  "ocr_fields": [
    {"field_id": "self_count", "text": "13", "confidence": 0.99}
  ],
  "turn_owner": null,
  "turn_observed_frames": 4,
  "turn_matching_frames": 0,
  "turn_latest_frame_matches": false,
  "latency_ms": 11.2,
  "source_commit": "<40 hex>",
  "config_sha256": "<64 hex>"
}
```

Ground-truth va prediction frame ID phai one-to-one; missing/extra fail.
OCR field ID trong moi frame phai one-to-one; duplicate/missing/extra fail.
Confidence va latency phai finite, dung range; bool khong duoc coi la number.
Button object phai co dung hai key `play|pass`. Turn owner chi duoc
`SELF|LEFT|TOP|RIGHT|null`, map truc tiep toi `SeatPosition` trong contracts.
OCR exact match la byte-for-byte sau JSON decode; khong trim, case-fold hoac sua text.
Tat ca prediction record trong mot bundle phai co cung `source_commit` va
`config_sha256`; mixed implementation/config la invalid.

## 6. Metric va gate semantics

Ket qua co enum/string status:

- `PASS`
- `FAIL`
- `INSUFFICIENT_DATA`
- `INVALID_BUNDLE`

Khong duoc gop `INSUFFICIENT_DATA` thanh `PASS`.

Thu tu quyet dinh status:

1. schema/checksum/path/integrity sai -> `INVALID_BUNDLE`;
2. bundle valid nhung co safety violation hoac metric co denominator bi duoi gate -> `FAIL`;
3. khong co failure nhung unlocked, thieu coverage hoac dung threshold ha thap -> `INSUFFICIENT_DATA`;
4. chi khi tat ca integrity, safety, metric va coverage gate dat -> `PASS`.

Metric bat buoc:

- `test_frames`;
- `test_sessions`, `test_sequences`, `unique_test_image_sha256`;
- `button_state_total`, `button_state_correct`, `button_exact_accuracy`;
- `negative_play_frames`, `false_play_enabled`;
- `critical_ocr_total`, `critical_ocr_correct`, `critical_ocr_exact_accuracy`;
- `low_confidence_ocr_non_unknown`;
- `turn_total`, `turn_exact`, `turn_exact_accuracy`;
- `false_my_turn`;
- `critical_turn_total`, `critical_consensus_violations`;
- latency `mean`, `p50`, `p95`, `max`;
- failure counts theo reason code.

Gate production mac dinh:

```text
locked bundle == true
test records reviewed == 100%
test_frames > 0
negative_play_frames >= 2000
test_sessions >= 5
test_sequences >= 50
unique_test_image_sha256 == test_frames
button_exact_accuracy >= 0.995
false_play_enabled == 0
critical_ocr_total > 0
critical_ocr_exact_accuracy >= 0.99
low_confidence_ocr_non_unknown == 0
turn_total > 0
false_my_turn == 0
critical_consensus_violations == 0
```

OCR threshold mac dinh `0.75`: prediction confidence thap hon threshold phai co
text exact `UNKNOWN`, neu khong la safety violation.

Critical turn co owner khac null chi hop le khi:

- `turn_observed_frames >= 4`;
- `turn_matching_frames >= 3`;
- `turn_latest_frame_matches == true`.

`false_my_turn` tang khi prediction la `SeatPosition.SELF` nhung expected khong
phai SELF, ke ca expected null.

`button_state_total` la so cap `(frame, button)` tren split test.
Mot cap chi correct khi ca `visible` va `enabled` exact match. OCR accuracy chi
dung field `critical=true`. Turn accuracy dung moi test frame co
`expected_turn_owner != null`; `critical_turn_total` dung moi frame
`critical_transition=true`. Moi denominator bang 0 phai tra `null` trong JSON,
khong duoc tra NaN, Infinity hoac tu coi la 100%.

Threshold phai nam trong typed config va duoc ghi vao output; CLI co the override
nhung khong duoc ha threshold ma van goi production PASS. Neu override thap hon
production default, status toi da la `INSUFFICIENT_DATA`.

## 7. Output deterministic

CLI:

```powershell
py -3 tools/evaluate_perception_ui.py `
  --bundle <bundle-dir> `
  --output <output-dir>
```

Output:

```text
metrics.json
failures.jsonl
evaluated_manifest.json
run_metadata.json
```

Yeu cau:

- `metrics.json`, `failures.jsonl`, `evaluated_manifest.json` byte deterministic;
- key sort, UTF-8/LF, khong NaN/Infinity;
- failure sort theo `frame_id`, `reason_code`;
- `evaluated_manifest` co SHA-256 input/output, threshold, source commit;
- timestamp/machine path chi trong `run_metadata.json`, khong lam artifact deterministic thay doi;
- khong ghi vao bundle input;
- output directory phai nam ngoai bundle input; overlap/self-reference la invalid;
- output temp + atomic replace de tranh artifact nua vo;
- repeat run cung input/config cho ba deterministic artifact giong byte.

CLI exit code:

- `0`: PASS;
- `1`: FAIL metric/safety;
- `2`: INSUFFICIENT_DATA;
- `3`: INVALID_BUNDLE/schema/checksum/path.

Khong bat exception stack trace voi loi du lieu binh thuong; in reason ro va exit dung code.

## 8. Test bat buoc

Chi tao `tests/test_perception_ui_evaluation.py`. Dung temporary directory,
synthetic PNG nho va fixture khong co secret.

Toi thieu test:

1. perfect locked bundle nho van `INSUFFICIENT_DATA` vi thieu 2.000 negatives;
2. bundle du coverage va perfect prediction `PASS`;
3. mot false enabled PLAY tren negative frame `FAIL`;
4. button accuracy duoi 99.5% `FAIL`;
5. critical OCR sai hoac duoi 99% `FAIL`;
6. low-confidence OCR khong tra `UNKNOWN` `FAIL`;
7. false `MY_TURN` `FAIL`;
8. critical turn 3/4 nhung latest=false `FAIL`;
9. missing/extra/duplicate frame prediction invalid;
10. duplicate OCR field invalid;
11. duplicate JSON key va NaN/Infinity invalid;
12. bool-as-int/float invalid;
13. path traversal, absolute path va symlink escape invalid;
14. checksum mismatch, image corrupt, viewport mismatch invalid;
15. test frame chua APPROVED invalid/insufficient theo documented rule;
16. unlocked bundle khong bao gio PASS;
17. deterministic output qua hai run;
18. input bundle byte-for-byte khong doi;
19. CLI exit code 0/1/2/3;
20. failure reason code va ordering deterministic;
21. source commit/config checksum sai format invalid;
22. max-record guard ngan input qua lon truoc khi ton bo nho.
23. duplicate image checksum trong test khong duoc tinh thanh coverage;
24. thieu 5 session hoac 50 sequence van `INSUFFICIENT_DATA`;
25. mixed source commit/config invalid;
26. enum turn sai, button key thieu/thua va OCR implicit normalization invalid.

Khong tao 2.000 image that trong test. Co the unit-test evaluator bang 2.000 typed
records in-memory; CLI/integrity test chi dung fixture nho.

## 9. Evidence

Tao `docs/acceptance/perception-ui/0.3.0/`:

- `README.md`
- `commands.txt`
- `metrics.json`
- `artifacts.sha256`
- `failures.md`
- `bundle_schema_v1.md`

Evidence phai ghi trung thuc:

- evaluator code/test complete;
- production dataset gate van chua dat;
- current committed data khong du 2.000 negatives/OCR/turn locked replay;
- module van `IN_PROGRESS`, khong `CANDIDATE`/`LOCKED`;
- task 01B la runner/calibration tren bundle duoc owner duyet.

Checksum manifest phai ASCII hoac UTF-8 no BOM, LF-only, lenh tao checksum phai
chay duoc nguyen van; khong dung placeholder `files=[...]`.

## 10. Adversarial review truoc delivery

Tu chay payload pha hoai ngoai happy-path tests:

- duplicate object key o moi level;
- wrong enum/string;
- non-finite number;
- huge/negative latency;
- duplicate normalized path;
- Windows path separator va case collision;
- frame ID Unicode/control character;
- output directory nam trong input bundle;
- source/prediction count mismatch;
- 2.000 negatives nhung tat ca cung frame ID;
- 2.000 frame ID khac nhau nhung cung image checksum;
- 2.000 frame trong mot session/sequence;
- mixed source commit hoac config checksum;
- metric denominator bang 0.

Moi truong hop phai fail explicit, khong crash mo ho, khong PASS.

## 11. Verification cuoi

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -p "test_perception_ui_evaluation.py" -v
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
git diff --check
git status --short
git diff --name-only gemini-perception-ui-01a-baseline...HEAD
```

Moi changed path phai nam trong whitelist. Khong sua test cu.

Commit:

```text
Add deterministic perception UI evaluation gate
```

Push `agent/gemini-perception-ui-01a`, mo draft PR voi `Relates to #8`.
Khong dung `Closes #8`, khong merge, khong doi label/status/module.

Final report tai:

`GEMINI_PERCEPTION_UI_01A_OUTPUT/FINAL_REPORT.md`

Bao cao bat buoc:

- branch + commit SHA;
- changed files;
- exact test totals;
- deterministic artifact hashes;
- gate nao code complete;
- gate nao blocked boi dataset;
- known limitations;
- exact next step cho 01B.
