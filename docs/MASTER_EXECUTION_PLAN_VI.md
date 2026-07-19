# Master Execution Plan - Tien Len Bot

Cập nhật: 2026-07-19

Mục tiêu của tài liệu này là để một agent mới có thể tiếp tục dự án mà không cần đọc
lại lịch sử chat. Đây là kế hoạch thực thi và tiêu chuẩn nghiệm thu; trạng thái máy đọc
được nằm tại `.github/module-registry.json`.

## 1. Mục tiêu cuối

Bot phải chạy trên MEmu/Windows, nhận đúng bàn chơi, đọc đúng state, chỉ quyết định khi
đủ chắc chắn, thao tác có xác minh và cô lập lỗi theo từng bot. Module đã nghiệm thu phải
có thể tái sử dụng trong phiên bản bot sau thông qua public API và Semantic Versioning.

Không coi dự án hoàn tất khi chỉ có model weight, unit test hoặc một vài action demo.
Production candidate phải qua offline test, replay, live read-only soak và action có giám
sát. Không tự bật unattended gameplay có rủi ro tài khoản hoặc tiền thật.

## 2. Definition of Done toàn dự án

- `main` chỉ nhận thay đổi qua PR và required checks đều xanh.
- Mọi module có owner, public API, dependency, version và trạng thái trong registry.
- Không còn đường tắt từ frame raw tới tap; luồng bắt buộc đi qua perception, state,
  consensus, decision, action guard và verification.
- Mọi action có `bot_id`, `frame_id`, `frame_ts`, confidence, decision reason và kết quả
  verification để replay.
- State stale, identity mismatch, signal conflict, timeout hoặc confidence thấp đều fail-safe.
- Single-bot vượt qua replay và live gates; multi-bot chứng minh cô lập identity/resource.
- Release có source commit, module versions, config schema, model checksum, metrics và
  hướng dẫn rollback.

## 3. Thứ tự triển khai bắt buộc

### Phase 0 - Governance và baseline

Deliverables:

- `AGENTS.md`, module registry, CODEOWNERS, PR template và CI quality gate.
- Một issue cho mỗi task; một branch/PR cho mỗi module nhỏ.
- Ghi baseline test và live evidence hiện có, không nâng trạng thái quá bằng chứng.

Gate: CI chạy được trên PR, module lock guard từ chối thay đổi `LOCKED` không được duyệt.

### Phase 1 - Contracts

Phạm vi: `contracts/` và test contract.

Yêu cầu:

- Card code duy nhất `3S..2H`; rank `3<...<A<2`; suit `S<C<D<H`.
- `PerceptionSnapshot`, `TableState`, action, verify và consensus có validation rõ ràng.
- Public symbols được document; thay đổi breaking phải bị compatibility test phát hiện.
- Có fixture serialize/deserialize ổn định nếu state đi qua process hoặc lưu replay.

Gate khóa:

- 100% contract tests pass trên Python versions được CI hỗ trợ.
- Không tồn tại encoding card thứ hai bên trong module production.
- Consumer tests của perception, state, decision và action đều pass.
- Owner review API và chốt version `contracts-v1.0.0`.

### Phase 2 - Game rules và decision engine

Phạm vi: luật Tiến Lên Miền Nam, enumerate legal moves và policy; không phụ thuộc ảnh/ADB.

Yêu cầu:

- Classify và so sánh: lẻ, đôi, sám, sảnh, tứ quý, ba đôi thông, bốn đôi thông và luật chặt.
- Kiểm tra luật mở đầu, vòng mới, pass, kết thúc ván và mọi edge case đã chốt.
- `enumerate_legal_moves(state)` không bỏ sót và không sinh nước bất hợp lệ.
- Policy v1 deterministic, chỉ trả legal action hoặc `WAIT`; không dùng ML/RL ở gate v1.

Gate khóa:

- Bảng test luật được chủ repo duyệt và 100% pass.
- Property/invariant tests xác nhận không trùng lá, không dùng lá ngoài hand và mọi PLAY hợp lệ.
- Replay decision trên fixture cố định cho kết quả lặp lại được.
- Không có action bất hợp lệ trong tối thiểu 10.000 state sinh kiểm thử.

### Phase 3 - Discovery, binding và capture

Phạm vi: `bot/discovery/`, `bot/capture/`, identity runtime và frame envelope.

Yêu cầu:

- Binding duy nhất `bot_id <-> vm_index <-> title <-> pid <-> hwnd <-> adb_serial`.
- Windows-side capture, viewport chuẩn hóa 1280x720, queue bounded/latest-only.
- Recheck identity trước action; frame luôn có source identity và timestamp.
- Không dùng `adb screencap` trong hot path.

Gate khóa:

- Parser/unit tests pass và negative tests từ chối duplicate/mismatch.
- Read-only soak tối thiểu 2 giờ trên mỗi layout hỗ trợ, không nhầm VM, không leak queue.
- Capture p95 `<= 50 ms` tại 1280x720/8 FPS trên máy đích; error rate `< 0.1%`.
- Window move/minimize/restore và emulator restart có recovery được ghi log.

### Phase 4 - Dataset và perception

Phạm vi: hand cards, table cards, buttons/OCR và turn signals. Tuân thủ
`agent_handoff_bundle/TRAINING_GUIDE_VI.md`.

Yêu cầu:

- Tách dữ liệu `MY_HAND`, `TABLE_PLAY`, `BUTTON_UI`; không trộn nút vào card taxonomy.
- Synthetic/pseudo bbox chỉ dùng bootstrap, không làm ground truth production.
- Split theo session/match/round; QA chéo 100% val/test và tối thiểu 20% train.
- Card model đúng 52 class và đúng thứ tự contract; artifact có checksum/model card.
- Turn owner chỉ chốt khi timer/highlight và card-count delta đồng thuận.

Gate khóa card candidate:

- `mAP50 >= 0.98`, `mAP50-95 >= 0.75`, không class vắng ở train/val/test.
- Hand precision/recall `>= 0.99`, exact hand set `>= 98%`, worst recall `>= 95%`.
- Table precision/recall `>= 0.98`, exact combo `>= 97%`, worst recall `>= 92%`.
- Inference p95 mỗi card model `<= 70 ms`; full perception p95 `<= 125 ms`.
- Không leakage theo SHA-256, pHash, session hoặc round.

Gate khóa button/OCR/turn:

- Button exact accuracy `>= 99.5%` và 0 false PLAY trên 2.000 negative/disabled frames.
- OCR field quan trọng exact `>= 99%`; confidence thấp trả `UNKNOWN`.
- Turn transition dùng `3/4` consensus, frame cuối thuộc nhóm; 0 false MY_TURN trên locked replay.

### Phase 5 - State extraction và consensus

Phạm vi: `bot/perception/table_state.py`, validation và adapter sang decision.

Yêu cầu:

- Ghép đúng my hand, selected cards, last combo, counts, turn owner, buttons và phase.
- State thường dùng `2/3`; transition quan trọng dùng `3/4`; latest frame bắt buộc đồng thuận.
- Từ chối duplicate card, stale frame, confidence thấp, identity mismatch và signal conflict.

Gate khóa:

- Locked replay có exact state `>= 98%` và 100% transition nguy hiểm đúng/fail-safe.
- Không phát decision từ state stale hoặc chưa consensus trong integration tests.
- Mọi mismatch có reason code và frame evidence.

### Phase 6 - Action và verification

Phạm vi: action plan, chọn lá, PLAY/PASS, ADB broker/controller và post-action verify.

Luồng bắt buộc:

1. Xác nhận identity, turn và state mới nhất.
2. Tap từng lá theo ROI của chính frame đã duyệt.
3. Recapture và xác nhận selection đã đổi đúng.
4. Xác nhận PLAY/PASS visible và enabled.
5. Tap nút đúng một lần.
6. ROI diff là primary; nếu fail sau retry thì parse hand count/state làm escalation.
7. Không xác minh được thì vào recovery/stop, không retry mù.

Gate khóa:

- Unit/integration tests bao phủ timeout, stale frame, missing button và partial selection.
- Tối thiểu 100 action thật có giám sát: 0 tap sai lá, 0 false PLAY, 0 action sai lượt.
- Mỗi action có trước/sau frame, tap coordinates, latency và verification reason.
- Timeout luôn fail-safe; không có vòng retry vô hạn.

### Phase 7 - Orchestrator, recovery và replay

Phạm vi: worker/supervisor, state machine, watchdog, event log và offline replay.

State tối thiểu:

- `WAITING_FOR_GAME`
- `DEALING_OR_SORTING`
- `WAITING_TURN`
- `MY_TURN_FREE`
- `MY_TURN_RESPONSE`
- `EXECUTING_ACTION`
- `RECOVERING`
- `STOPPED`

Gate khóa:

- Decision chỉ được gọi trong hai state `MY_TURN_*`.
- Replay tái tạo được perception/state/decision/action/verify mà không cần MEmu.
- Fault injection cho stale frame, capture loss, ADB timeout, model error và popup đều fail-safe.
- Recovery một worker không restart worker khác.

### Phase 8 - Single-bot production candidate

Gate:

- Replay toàn bộ locked dataset với metrics đạt Phase 4-7.
- Read-only soak tối thiểu 2 giờ hoặc 20 ván, không tap.
- Sau đó chạy tối thiểu 100 supervised verified actions đạt 0 lỗi an toàn.
- Chạy nhiều ván liên tiếp có dealing, lead, response, pass, end và restart.
- Có panic stop, operator log, config snapshot và rollback procedure.

### Phase 9 - Multi-bot

Gate:

- Tối thiểu 2 MEmu chạy đồng thời; mục tiêu cuối theo resource budget của máy.
- 0 frame/action bị route nhầm `bot_id`, `hwnd` hoặc `adb_serial`.
- Queue overload chỉ drop frame cũ, không làm action dùng state cũ.
- Kill/restart một VM không ảnh hưởng session còn lại.
- Soak tối thiểu 2 giờ với CPU/RAM/GPU/queue/latency report.

### Phase 10 - Release và tái sử dụng

Mỗi module `LOCKED` dùng Semantic Versioning:

- `PATCH`: sửa lỗi không đổi public API.
- `MINOR`: thêm khả năng tương thích ngược.
- `MAJOR`: breaking contract và bắt buộc migration guide.

Release manifest phải ghi source commit, module versions, config schema, model checksum,
supported viewport/theme, metrics, evidence location và known limitations. Bot phiên bản sau
chỉ phụ thuộc public API/version; không import file nội bộ của module.

## 4. Thứ tự claim đề xuất cho agent tiếp theo

1. `GOV-01`: hoàn tất GitHub branch protection/required checks.
2. `CONTRACT-01`: serialization + compatibility fixtures, đưa contracts thành lock candidate.
3. `RULES-01`: xây module luật đầy đủ và exhaustive tests.
4. `REPLAY-01`: recorder/viewer offline trước khi mở rộng live action.
5. `DATA-01`: inventory, dedup, split và annotation QA.
6. `PERCEPTION-HAND-01` và `PERCEPTION-TABLE-01`: chạy song song sau DATA-01.
7. `PERCEPTION-UI-01`: button/OCR/turn locked replay.
8. `STATE-01`: nối perception thật vào typed state.
9. `ACTION-01`: hoàn tất two-stage verification và supervised gate.
10. `ORCH-01`: state machine/recovery end-to-end.
11. `E2E-01`: single-bot soak.
12. `MULTI-01`: multi-bot isolation soak.

Không claim task phụ thuộc khi dependency chưa đạt ít nhất `CANDIDATE`.

## 5. Evidence và artifact bắt buộc

Artifact nhẹ được commit dưới `docs/acceptance/<module>/<version>/`. Dataset, video, log lớn
và weights lưu ngoài Git hoặc GitHub Release; repo chỉ giữ manifest, checksum và link.

Mỗi evidence bundle tối thiểu có:

- `README.md`: môi trường, commit, scope và kết luận;
- `commands.txt`: lệnh chạy thật;
- `metrics.json`: metric máy đọc được;
- `artifacts.sha256`: checksum;
- `failures.md`: lỗi còn lại và quyết định chấp nhận/không chấp nhận.

## 6. Cách bàn giao khi hết token

Agent phải cập nhật issue/PR trước khi dừng. Dùng đúng mẫu:

```text
Task/Module:
Branch + commit:
Files changed:
Completed:
Not completed:
Tests run + exact result:
Evidence/artifact:
Known risks:
Exact next command/step:
```

Nếu chưa đủ gate, giữ trạng thái `IN_PROGRESS` hoặc `CANDIDATE`; tuyệt đối không tự ghi `LOCKED`.
