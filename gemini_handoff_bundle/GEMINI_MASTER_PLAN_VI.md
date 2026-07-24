# Gemini Master Plan

## 1. Mục tiêu cuối

Hoàn thiện bot Tiến Lên chạy trên MEmu/Windows theo đường đi bắt buộc:

```text
MEmu identity -> Windows capture -> perception -> typed state -> consensus
-> deterministic legal decision -> guarded selection/action -> verification
-> recovery/replay -> supervised production qualification
```

Không nối raw frame trực tiếp tới tap. Mọi uncertainty, stale state, identity mismatch, signal conflict hoặc timeout phải trả `WAIT`, recovery hoặc stop.

## 2. Cơ chế thực thi an toàn

- Một task, một branch, một draft PR.
- Chỉ task có `status=ACTIVE` trong `ACTIVE_TASK.json` được phép làm.
- Mọi path mặc định bị cấm; whitelist chỉ có hiệu lực cho active task.
- Không sửa file hiện hữu nếu `allowed_existing_file_modifications` không nêu rõ.
- Không tự đóng issue, merge PR, đổi registry, tạo tag hoặc tuyên bố `LOCKED`.
- Không dùng tài khoản/admin token của chủ repo.
- Không chạy unattended gameplay hoặc action có rủi ro tài khoản/tiền thật.
- Artifact lớn, raw dataset và weights không commit vào Git; chỉ commit manifest/checksum/link.

## 3. Thứ tự task toàn dự án

### G0 - Baseline/governance

Trạng thái: đã có branch protection, CI, CODEOWNERS, registry và 84 tests. Gemini chỉ xác minh, không chỉnh trong DATA-01.

### G1 - DATA-01, issue #5

Trạng thái: code inventory đã merge; production gate vẫn `BLOCKED`.

Kết quả: inventory, SHA-256/pHash dedup, split chống leakage, annotation QA,
coverage report đã có. Dataset hiện chỉ có 36 ảnh MY_HAND, 0 bbox production,
0 val/test, 0 TABLE_PLAY và thiếu hard-negative; không được train production.

Gate: raw không đổi; leakage bằng 0; reports deterministic; 100% val/test và ít nhất 20% train được chọn second review.

### G2 - CONTRACT-01, issue #2

Trạng thái: `0.2.0 CANDIDATE`, PR #26 đã merge và có 182 tests.

Kết quả: strict bidirectional serialization, compatibility fixtures, duplicate
JSON rejection và source-object validation. Chưa `LOCKED`; chỉ owner quyết định lock/tag.

### G3 - REPLAY-01, issue #4

Trạng thái: code/evidence `0.1.0 CANDIDATE`; issue đã đóng.

Kết quả: recorder/reader versioned, deterministic offline replay, checksums, malformed/stale evidence rejection.

### G4 - PERCEPTION-HAND-01 và TABLE-01, issues #6/#7

Trạng thái: blocked đến khi DATA-01 được nghiệm thu.

Hand và table là hai dataset/model riêng. Đúng 52 class theo contract. Gate: mAP50 >= 0.98, mAP50-95 >= 0.75; hand exact set >= 98%; table exact combo >= 97%; p95 mỗi model <= 70 ms; zero leakage.

### G5 - PERCEPTION-UI-01, issue #8

Trạng thái: `GEMINI-PERCEPTION-UI-01A` đang `ACTIVE`.

Task 01A chỉ xây locked-replay bundle schema, evaluator deterministic, metric
gate và CLI fail-safe. Không calibration detector và không claim production.

Task 01B chỉ được mở sau review 01A và sau khi có bundle được duyệt. Gate cuối:
button exact >= 99.5%; zero false PLAY trên ít nhất 2.000 negative/disabled
frames; OCR critical exact >= 99%; low confidence UNKNOWN; zero false MY_TURN
trên locked replay với hybrid agreement và 3/4 latest-frame consensus.

### G6 - STATE-01, issue #9

Trạng thái: blocked đến production perception.

Gate: exact state >= 98% locked replay; regular 2/3, critical 3/4, latest frame đồng thuận; stale/duplicate/conflict fail-safe.

### G7 - ACTION-01, issue #10

Trạng thái: blocked đến UI/turn/state.

Gate: identity + fresh turn guard, chọn lá theo approved frame, recapture selection, enabled button, bounded tap, ROI diff primary và hand-count escalation. 100 supervised actions: zero wrong card, false PLAY và out-of-turn action.

### G8 - ORCH-01, issue #11

Trạng thái: blocked đến rules/replay/state/action.

State machine tối thiểu: WAITING_FOR_GAME, DEALING_OR_SORTING, WAITING_TURN, MY_TURN_FREE, MY_TURN_RESPONSE, EXECUTING_ACTION, RECOVERING, STOPPED. Fault một bot không restart bot khác.

### G9 - E2E-01, issue #12

Trạng thái: blocked đến module gates.

Gate: locked replay pass; read-only soak >= 2 giờ hoặc 20 ván; sau đó 100 supervised verified actions; panic stop, logs, config snapshot và rollback.

### G10 - MULTI-01, issue #13

Trạng thái: blocked đến single-bot candidate.

Gate: ít nhất 2 VM trong 2 giờ; zero cross-route bot_id/hwnd/adb_serial; restart một VM không ảnh hưởng VM còn lại.

## 4. Quy trình mở task tiếp theo

Chỉ chủ repo/Codex được:

1. Review PR và evidence task hiện tại.
2. Merge hoặc yêu cầu sửa trong cùng branch.
3. Cập nhật module/issue nếu evidence đủ.
4. Thay `ACTIVE_TASK.json` bằng policy mới qua một PR riêng.
5. Tạo baseline tag mới cho task kế tiếp.

Gemini không được coi task catalog là whitelist và không được tự sửa `ACTIVE_TASK.json`.

## 5. Điều kiện hoàn thành dự án

Unit test hoặc một vài demo không đủ. Dự án chỉ production-ready khi locked replay, model metrics, capture soak, state exactness, 100 supervised actions, single-bot soak và multi-bot isolation đều có evidence/checksum có thể chạy lại.

## 6. Active override - 2026-07-24

`GEMINI-PERCEPTION-UI-01A` da merge tai PR #28. Evaluator `0.3.0` duoc chap
nhan, nhung production data gate van `BLOCKED` va `MOD-PERCEPTION` van
`IN_PROGRESS`.

Task dang `ACTIVE` la `GEMINI-PERCEPTION-UI-01B`: read-only inference runner tao
prediction evaluator-compatible. Chi file trong `ACTIVE_TASK.json` duoc cap
quyen. Calibration va production qualification se la 01C rieng sau khi owner
duyet locked dataset; Gemini khong duoc tu bat dau.

## 7. Training data lock (owner-approved addendum)

The detailed, enforceable training requirements are maintained in
`docs/TRAINING_PLAN_FINAL.md`. Agents must treat that file as the source of
truth for dataset intake, annotation, split, training, and production gates.

The current dataset remains `BLOCKED_ON_DATA`: it has only the legacy 36
`MY_HAND` images, no production annotations, no real validation/test split,
and no locked UI-negative set. No agent may train or claim production
qualification until the checklist in `docs/TRAINING_PLAN_FINAL.md` is complete.

`GEMINI-PERCEPTION-UI-01B` delivery is complete and its task policy is now
`PAUSED_FOR_OWNER_REVIEW`. Gemini must stop when `guard_scope.ps1` reports
that no ACTIVE task is authorized. A new Gemini coding task requires a new
owner-approved policy and baseline; agents must not reactivate this policy.
