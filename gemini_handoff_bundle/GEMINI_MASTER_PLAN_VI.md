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

Trạng thái: `ACTIVE`.

Kết quả: inventory, SHA-256/pHash dedup, split chống leakage, annotation QA, coverage report. Không train.

Gate: raw không đổi; leakage bằng 0; reports deterministic; 100% val/test và ít nhất 20% train được chọn second review.

### G2 - CONTRACT-01, issue #2

Trạng thái: chờ owner mở active policy mới.

Kết quả: serialization/compatibility fixtures, consumer compatibility. Chỉ owner quyết định lock/tag.

### G3 - REPLAY-01, issue #4

Trạng thái: chờ G2 review.

Kết quả: recorder/reader versioned, deterministic offline replay, checksums, malformed/stale evidence rejection.

### G4 - PERCEPTION-HAND-01 và TABLE-01, issues #6/#7

Trạng thái: blocked đến khi DATA-01 được nghiệm thu.

Hand và table là hai dataset/model riêng. Đúng 52 class theo contract. Gate: mAP50 >= 0.98, mAP50-95 >= 0.75; hand exact set >= 98%; table exact combo >= 97%; p95 mỗi model <= 70 ms; zero leakage.

### G5 - PERCEPTION-UI-01, issue #8

Trạng thái: code safety đã có, production evidence còn thiếu.

Gate: button exact >= 99.5%; zero false PLAY trên ít nhất 2.000 negative/disabled frames; OCR critical exact >= 99%; low confidence UNKNOWN; zero false MY_TURN trên locked replay với hybrid agreement và 3/4 latest-frame consensus.

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
