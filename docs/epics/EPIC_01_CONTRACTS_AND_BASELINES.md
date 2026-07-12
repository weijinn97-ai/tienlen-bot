# Epic 01 - Contracts and Baselines

## Mục tiêu

Chuẩn hóa contract giữa các lane `capture -> perception -> state -> decision -> action` trước khi giao nhiều agent code song song.

## Kết quả cần có

- `contracts/interfaces.py` là source of truth cho:
  - card encoding `"{rank}{suit}"`, ví dụ `3S`, `10D`, `AH`
  - thứ tự Tiến Lên: rank `3<4<...<K<A<2`, suit `S<C<D<H`
  - `TableState`
  - `VerifySpec`
  - `ActionPlan`
  - regular consensus `2/3`
  - transition consensus `3/4`
- naming hiện có được audit để biết chỗ nào còn dùng contract cũ như `last_played_cards`
- issue template chung để agent mở issue theo cùng format

## In scope

- thiết kế interface layer
- enum, dataclass, validation helpers
- doc acceptance criteria
- test import + validation cơ bản cho contract

## Out of scope

- refactor toàn bộ runtime hiện tại sang contract mới trong cùng epic
- huấn luyện model
- action thật trên thiết bị

## Child issues gợi ý

1. Tạo `contracts/interfaces.py` và test contract.
2. Audit chỗ đang dùng state cũ trong `bot/agent/`, `bot/runtime/`.
3. Tạo issue template + epic docs để chia lane.

## Acceptance criteria

- [ ] Có file `contracts/interfaces.py` import được, không lỗi syntax.
- [ ] Contract có `TableState`, `CardCombo`, `ActionPlan`, `VerifySpec`, `ConsensusSpec`.
- [ ] Card encoding chuẩn hóa đúng `S/C/D/H`.
- [ ] Có constant consensus `2/3` cho hành động thường và `3/4` cho transition quan trọng.
- [ ] Có test unit cho card validation, state validation và action validation.

## Dependency

- không phụ thuộc model hoặc gameplay loop

## Giao việc phù hợp cho agent

- agent thiên backend/contracts
- agent review naming/runtime boundary
