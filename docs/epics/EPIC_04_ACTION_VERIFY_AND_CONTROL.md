# Epic 04 - Action, Verify, and Playable Loop

## Mục tiêu

Cho bot bấm thật nhưng vẫn có lớp an toàn đủ để không bị hành động mù, rồi nối lane này thành single-bot playable demo đủ để review nội bộ.

## Verify chốt

Primary:

- ROI diff theo `verify_spec = {roi, expected_change, timeout_ms, max_retries}`

Escalation:

- nếu ROI diff fail sau retries thì parse lại hand count trước khi báo lỗi lên supervisor

Nói ngắn:

- A là primary
- B là escalation

## Kết quả cần có

- `ActionPlan` rõ loại action
- mapping cards/buttons -> coordinates
- `VerifySpec` đi cùng action
- verify sau action với ROI diff trước
- escalation parse hand count nếu nghi ngờ
- single-bot flow đi được từ `TableState -> Decision -> Action -> Verify`
- hook lỗi verify/action về supervisor theo hướng operator-safe

## In scope

- play/pass action contract
- verify primary bằng ROI diff
- escalation bằng hand count reparse
- error propagation lên supervisor
- single-bot playable demo
- trace log đủ để review nội bộ

## Out of scope

- tối ưu chiến lược chơi nâng cao
- multi-bot production hardening đầy đủ

## Child issues gợi ý

1. Thiết kế `ActionPlan` theo contract.
2. Map card/button ROI và tap sequence.
3. Thêm verify primary ROI diff.
4. Thêm escalation parse hand count.
5. Nối `DecisionOrchestrator -> ActionExecutor -> Verify`.
6. Chạy demo 1 bot thật với log đầy đủ.

## Acceptance criteria

- [x] `ActionPlan` phân biệt được play/pass/wait.
- [x] `VerifySpec` có đủ `roi`, `expected_change`, `timeout_ms`, `max_retries`.
- [x] Sau action, verify chạy ROI diff trước.
- [x] Nếu verify fail sau retries, có escalation parse hand count.
- [ ] Nếu cả A và B đều fail thì supervisor nhận lỗi rõ nguyên nhân.
- [ ] Có single-bot flow đi được từ frame/state đến action có verify.
- [ ] Có demo session thật ở mức review nội bộ.

## Trạng thái triển khai

- Action ROI mapping, ADB tap sequence, ROI diff và hand-count escalation đã có code/test.
- Live ADB tap + ROI verification đã pass bằng thao tác Cài đặt an toàn; xem `docs/LIVE_VALIDATION_2026-07-13.md`.
- Chưa tick playable loop/supervisor vì thiếu card weights và action-button data từ gameplay thật.

## Dependency

- phụ thuộc `EPIC_03`
- là cầu nối trước khi mở rộng multi-bot hardening sâu hơn

## Giao việc phù hợp cho agent

- agent action/runtime
- agent capture verify
- agent runtime integration
