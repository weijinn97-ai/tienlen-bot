# Full GitHub Handoff - Tien Len Bot

Cập nhật: 2026-07-19  
Repository: https://github.com/weijinn97-ai/tienlen-bot  
Branch chính: `main`  
Baseline khi tạo tài liệu: `09366d1`  
Roadmap GitHub: https://github.com/weijinn97-ai/tienlen-bot/issues/14

Tài liệu này là bản bàn giao một file dành cho agent mới. Đọc hết file trước khi claim
task. Không dùng lịch sử chat làm source of truth.

## 1. Agent cần làm gì trong 5 phút đầu

1. Clone repo và checkout `main` mới nhất.
2. Đọc `AGENTS.md`, file này và issue được giao.
3. Kiểm tra `.github/module-registry.json` để biết module, dependency và trạng thái.
4. Chỉ claim issue có nhãn `agent-ready`; không làm issue `blocked`.
5. Comment claim, tạo branch riêng, chỉ sửa file trong scope.
6. Chạy toàn bộ test trước PR; không push trực tiếp vào `main`.

Lệnh bắt đầu:

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git
cd tienlen-bot
git status -sb
git log -1 --oneline
py -3 -m pip install -r requirements-runtime.txt
py -3 tools/check_module_governance.py
py -3 -m unittest discover -s tests -v
```

Nếu làm perception/model:

```powershell
py -3 -m pip install -r requirements-perception.txt
```

## 2. Mục tiêu dự án

Xây bot Tiến Lên chạy trên MEmu/Windows với các nguyên tắc:

- một bot gắn đúng một VM/window/ADB identity;
- capture nhanh từ Windows, không dùng `adb screencap` trong hot path;
- perception và state phải đủ chắc chắn trước khi quyết định;
- action luôn có guard và post-action verification;
- lỗi một bot không làm ảnh hưởng bot khác;
- module đạt nghiệm thu được version hóa, khóa và tái sử dụng cho bot đời sau.

Dự án **chưa production-ready**. Hiện đã có foundation, live proof nhỏ và 69 unit/regression
tests, nhưng còn thiếu model production, luật đầy đủ, replay, soak dài và end-to-end gate.

## 3. Source of truth

Ưu tiên theo thứ tự:

1. `AGENTS.md`: quy tắc bắt buộc cho agent.
2. `docs/MASTER_EXECUTION_PLAN_VI.md`: phase và acceptance gate đầy đủ.
3. `.github/module-registry.json`: trạng thái/version/path/dependency máy đọc được.
4. GitHub issue được giao.
5. Contract và tests của module.
6. `agent_handoff_bundle/`: snapshot lịch sử và hướng dẫn train chi tiết.

Nếu có mâu thuẫn, dừng và hỏi chủ repo; không tự thay kiến trúc.

## 4. Kiến trúc và đường đi dữ liệu

```text
MEmu identity discovery
  -> Windows viewport capture (latest-only frame)
  -> perception: cards + buttons/OCR + hybrid turn signal
  -> PerceptionSnapshot
  -> validation + TableState assembly
  -> 2/3 regular or 3/4 critical consensus
  -> legal rules + deterministic decision
  -> guarded card selection
  -> recapture + button enabled verification
  -> PLAY/PASS tap
  -> ROI diff primary verification
  -> hand/state escalation verification
  -> success or RECOVERING/STOP
  -> replay/evidence log
```

Không được nối tắt frame raw trực tiếp tới tap.

## 5. Quyết định contract đã chốt

- Card code: `"{rank}{suit}"`, ví dụ `3S`, `10D`, `AH`, `2H`.
- Rank: `3<4<5<6<7<8<9<10<J<Q<K<A<2`.
- Suit: `S<C<D<H`; `S` Bích, `C` Chuồn, `D` Rô, `H` Cơ.
- Contract level dùng string; decision nội bộ có thể map int nhưng không đổi boundary.
- `TableState` gồm my cards, selected cards, last combo, four counts, turn owner,
  buttons, game phase, frame ID/timestamp và confidence.
- State thường: `2/3` frames và frame cuối thuộc nhóm đồng thuận.
- Transition bắt đầu/kết thúc ván hoặc tới lượt mình: `3/4` frames và latest-frame rule.
- Turn owner là hybrid: timer/highlight avatar + card-count delta; không khớp thì UNKNOWN.
- Verification: ROI diff là primary; hand/state count là escalation sau bounded retries.
- Confidence thấp, stale frame, identity mismatch hoặc conflict đều phải `WAIT`/fail-safe.

## 6. Bản đồ code

| Khu vực | Vai trò |
|---|---|
| `contracts/` | Public dataclass/enum và card/state/action/verify contracts |
| `bot/discovery/` | Scan MEmu, window, PID và ADB identity |
| `bot/capture/` | Windows capture, viewport và latest-frame buffer |
| `bot/perception/` | Card, button, OCR, turn owner và state assembly |
| `bot/agent/` | State adapter, local/API decision và orchestration boundary |
| `bot/actions/` | ADB broker/controller, action plan và verification |
| `bot/runtime/` | Worker, supervisor, schema và validation |
| `bot/inference/` | Shared inference queue/backend |
| `bot/stability/` | Watchdog, monitor và circuit breaker |
| `bot/ui/` | Operator launcher |
| `tools/` | Scanner, soak, action smoke, data intake và governance |
| `tests/` | Unit, sample-frame và live-regression tests |
| `data/` | Raw submissions, inbox và lightweight templates |
| `docs/` | Architecture, epics, validation và master plan |
| `agent_handoff_bundle/` | Historical full handoff, training guide và dashboard |

## 7. Trạng thái module hiện tại

Không module nào đang `LOCKED`. Chỉ chủ repo được khóa sau acceptance evidence.

| Module | Status | Đã có | Còn thiếu trước khi khóa |
|---|---|---|---|
| `MOD-CONTRACTS` | CANDIDATE `0.1.0` | Typed contracts và tests | Serialization/compatibility fixtures, owner API review |
| `MOD-DISCOVERY-CAPTURE` | CANDIDATE `0.1.0` | Discovery, viewport, 30s live proof | Soak 2 giờ, restart/move/minimize recovery |
| `MOD-PERCEPTION` | IN_PROGRESS `0.1.0` | Fallback, YOLO guard, button templates, hybrid turn | Production dataset/models, locked replay metrics |
| `MOD-STATE` | CANDIDATE `0.1.0` | Typed assembly, validation, 2/3 và 3/4 consensus | Production perception input và locked replay |
| `MOD-RULES-DECISION` | IN_PROGRESS `0.1.0` | Basic local fallback/single response | Luật đầy đủ, legal enumeration, 10k state invariant |
| `MOD-ACTIONS` | CANDIDATE `0.1.0` | Two-stage selection/action path, two live actions | 100 supervised actions và failure matrix |
| `MOD-RUNTIME` | IN_PROGRESS `0.1.0` | Worker/supervisor/watchdog scaffold | Full state machine, recovery, replay integration |
| `MOD-OPERATOR-UI` | IN_PROGRESS `0.1.0` | Launcher/start-stop/log | Preview, panic/recovery UX và tests |
| `MOD-REPLAY` | PLANNED `0.0.0` | Chưa có production module | Versioned recorder/viewer và deterministic replay |
| `MOD-MULTIBOT` | PLANNED `0.0.0` | Foundation/binding concepts | Concurrent identity/isolation soak |

## 8. Những gì đã xác minh

- Full local suite hiện có `69` tests pass.
- GitHub Actions `unit-and-governance` đang xanh trên `main`.
- VM 203 từng capture 239 frames/30 giây, 1280x720, 0 errors, p95 43.064 ms.
- Safe-UI ADB tap và ROI verification đã pass.
- Hai gameplay actions thật đã thực hiện có giám sát: `7S` và `3D`.
- Fixed-layout fallback đọc đúng các regression hands 13/12/11 trong sample hiện có.
- Hybrid turn detector chỉ chốt khi highlight và count delta đồng thuận.
- YOLO adapter từ chối weight sai 52-class taxonomy.
- Bootstrap YOLO cũ có `mAP50=0` và đã bị loại, không được dùng production.

Evidence hiện có: `docs/LIVE_VALIDATION_2026-07-13.md`.

## 9. Những gì chưa được coi là hoàn tất

- Chưa có production 52-class weights đạt locked test.
- Chưa có dataset bbox đủ coverage/QA và split chống leakage.
- Chưa có complete Tien Len rules/legal move engine.
- Chưa có deterministic replay module.
- Chưa nối production card/button/OCR vào full typed state liên tục.
- Chưa có production state machine/recovery end-to-end.
- Chưa qua read-only soak 2 giờ/20 ván.
- Chưa qua 100 supervised verified actions với 0 safety errors.
- Chưa có single-bot release candidate hoặc multi-bot isolation qualification.

## 10. GitHub backlog

Parent roadmap: https://github.com/weijinn97-ai/tienlen-bot/issues/14

### Agent có thể claim ngay

- #2 `CONTRACT-01`: https://github.com/weijinn97-ai/tienlen-bot/issues/2
- #3 `RULES-01`: https://github.com/weijinn97-ai/tienlen-bot/issues/3
- #4 `REPLAY-01`: https://github.com/weijinn97-ai/tienlen-bot/issues/4
- #5 `DATA-01`: https://github.com/weijinn97-ai/tienlen-bot/issues/5
- #8 `PERCEPTION-UI-01`: https://github.com/weijinn97-ai/tienlen-bot/issues/8

### Chưa được claim vì dependency

- #6 `PERCEPTION-HAND-01`, sau DATA-01:
  https://github.com/weijinn97-ai/tienlen-bot/issues/6
- #7 `PERCEPTION-TABLE-01`, sau DATA-01:
  https://github.com/weijinn97-ai/tienlen-bot/issues/7
- #9 `STATE-01`, sau production perception:
  https://github.com/weijinn97-ai/tienlen-bot/issues/9
- #10 `ACTION-01`, sau UI/turn và state:
  https://github.com/weijinn97-ai/tienlen-bot/issues/10
- #11 `ORCH-01`, sau rules/replay/state/action:
  https://github.com/weijinn97-ai/tienlen-bot/issues/11
- #12 `E2E-01`, sau module gates:
  https://github.com/weijinn97-ai/tienlen-bot/issues/12
- #13 `MULTI-01`, sau single-bot candidate:
  https://github.com/weijinn97-ai/tienlen-bot/issues/13

## 11. Acceptance gate tóm tắt

### Contracts

- Public API documented, round-trip fixtures và consumer tests pass.
- Không có encoding card thứ hai.
- Owner review và tag `contracts-v1.0.0` trước khi LOCKED.

### Rules/decision

- Đủ combo/rules đã chốt và deterministic legal enumeration.
- Mọi PLAY dùng đúng cards trong hand và hợp lệ.
- Không invalid action trong tối thiểu 10.000 generated states.

### Capture/binding

- 0 identity mismatch trong soak.
- Read-only soak ít nhất 2 giờ mỗi supported layout.
- Capture p95 `<= 50 ms` ở 1280x720/8 FPS; error rate `< 0.1%`.

### Hand/table cards

- Đúng 52 class và class order; không leakage.
- `mAP50 >= 0.98`, `mAP50-95 >= 0.75`.
- Hand exact set `>= 98%`, precision/recall `>= 0.99`, worst recall `>= 95%`.
- Table exact combo `>= 97%`, precision/recall `>= 0.98`, worst recall `>= 92%`.
- p95 mỗi card model `<= 70 ms`; full perception `<= 125 ms`.

### Button/OCR/turn

- Button exact `>= 99.5%`; 0 false PLAY trên 2.000 negative/disabled frames.
- Critical OCR exact `>= 99%`; confidence thấp trả UNKNOWN.
- 0 false MY_TURN trên locked replay.

### State/action

- Locked replay exact state `>= 98%`; dangerous transition đúng hoặc fail-safe 100%.
- 100 supervised actions: 0 wrong card, 0 false PLAY, 0 out-of-turn action.
- Không blind retry; timeout phải recovery/stop.

### End-to-end

- Locked replay pass.
- Read-only soak >= 2 giờ hoặc 20 ván.
- 100 supervised verified actions đạt 0 safety errors.
- Multi-bot: >= 2 VM/2 giờ, 0 cross-route identity/action.

Chi tiết đầy đủ nằm trong `docs/MASTER_EXECUTION_PLAN_VI.md` và từng issue.

## 12. Dataset và train model

Nguồn ảnh người dùng:

```text
data/inbox/user_training_images/raw/
  fullscreen/
  my_hand/
  table_plays/
  buttons_ui/
```

Quy tắc bắt buộc:

- Không sửa/xóa/đổi tên raw inputs.
- Không dùng `configs/dataset.yaml` cũ cho production.
- Không dùng pseudo bbox hoặc bootstrap weight làm production truth.
- Tách hand cards và table cards; buttons/OCR là pipeline riêng.
- Split theo session/match/round, không random từng frame.
- 100% val/test và ít nhất 20% train được review chéo.
- Artifact phải có model card, dataset stats, metrics, latency và checksum.

Hướng dẫn đầy đủ: `agent_handoff_bundle/TRAINING_GUIDE_VI.md`.

## 13. Quy trình GitHub và khóa module

`main` hiện được bảo vệ:

- bắt buộc Pull Request;
- tối thiểu 1 approval;
- CODEOWNER review;
- dismiss stale approvals và approve latest push;
- required check `unit-and-governance`;
- resolve conversations;
- chặn force-push và branch deletion.

Lifecycle:

```text
PLANNED -> IN_PROGRESS -> CANDIDATE -> LOCKED -> DEPRECATED
```

Để khóa module:

1. Hoàn tất toàn bộ gate và evidence.
2. Mở PR có label `module-lock-candidate`.
3. Ghi public API, version và compatibility.
4. Owner review evidence.
5. Cập nhật registry sang `LOCKED` và stable version.
6. Merge, tạo tag `<module-id>-v<version>` và release manifest.

Để sửa module LOCKED:

1. Mở issue riêng và xác định PATCH/MINOR/MAJOR.
2. Owner gắn `locked-change-approved`.
3. Thêm regression test trước khi sửa.
4. Chạy lại gate module và consumer modules.
5. Update version/evidence/migration trong cùng PR.

Không cấp admin token của `weijinn97-ai` cho agent; admin có thể bypass branch protection.

## 14. Quy tắc PR cho agent

- Một issue = một branch/PR; không gộp refactor không liên quan.
- Không chỉnh module ngoài scope hoặc đổi contract ngầm.
- Không commit `.env`, secret, raw dataset lớn, weights hoặc log nhạy cảm.
- Không gọi task hoàn tất chỉ vì unit tests xanh.
- Failure path phải explicit và operator-safe.
- PR phải ghi command và kết quả test thật.

Lệnh tối thiểu trước PR:

```powershell
py -3 tools/check_module_governance.py
py -3 -m unittest discover -s tests -v
git diff --check
```

## 15. Handoff khi agent hết token

Agent phải cập nhật issue/PR bằng mẫu sau:

```text
Task/Module:
Branch + commit SHA:
Files changed:
Completed:
Not completed:
Tests run + exact result:
Evidence/artifact + checksum:
Known risks:
Exact next command/step:
```

Không để quyết định, lỗi hoặc bước tiếp theo chỉ tồn tại trong chat riêng.

## 16. Checklist agent trước khi bắt đầu code

- [ ] Đã đọc `AGENTS.md` và file này.
- [ ] Issue có `agent-ready`, chưa có agent khác claim.
- [ ] Dependency đạt trạng thái yêu cầu.
- [ ] Scope file và public API đã rõ.
- [ ] Branch tạo từ `main` mới nhất.
- [ ] Không đụng module `LOCKED`.
- [ ] Acceptance criteria có thể đo được.
- [ ] Biết artifact/evidence phải trả.
- [ ] Biết lệnh test và failure behavior.
- [ ] Sẽ cập nhật issue/PR trước khi hết phiên.

## 17. Link quan trọng

- Repo: https://github.com/weijinn97-ai/tienlen-bot
- Master roadmap issue: https://github.com/weijinn97-ai/tienlen-bot/issues/14
- Master plan:
  https://github.com/weijinn97-ai/tienlen-bot/blob/main/docs/MASTER_EXECUTION_PLAN_VI.md
- Agent rules:
  https://github.com/weijinn97-ai/tienlen-bot/blob/main/AGENTS.md
- Module registry:
  https://github.com/weijinn97-ai/tienlen-bot/blob/main/.github/module-registry.json
- Training guide:
  https://github.com/weijinn97-ai/tienlen-bot/blob/main/agent_handoff_bundle/TRAINING_GUIDE_VI.md
- Live evidence:
  https://github.com/weijinn97-ai/tienlen-bot/blob/main/docs/LIVE_VALIDATION_2026-07-13.md
- Issues:
  https://github.com/weijinn97-ai/tienlen-bot/issues
- Actions:
  https://github.com/weijinn97-ai/tienlen-bot/actions

Agent mới chỉ cần nhận link file này và link issue được giao để bắt đầu đúng hướng.
