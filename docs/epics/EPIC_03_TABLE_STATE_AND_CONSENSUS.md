# Epic 03 - Table State and Consensus

## Mục tiêu

Biến output từ perception/UI signals thành `TableState` mà decision engine và action lane có thể dùng ổn định.

## Contract chốt

`TableState` gồm:

- `my_cards[]`
- `last_played_combo`
- `player_card_counts[4]`
- `turn_owner`
- `buttons[]`
- `game_phase`
- `frame_ts`
- `confidence`

## Ý nghĩa

Decision engine không thể đánh đúng nếu thiếu:

- `last_played_combo`
- `player_card_counts`
- `turn_owner`

## Consensus chốt

- hành động thường: `2/3` frames
- điều kiện thêm: frame cuối phải nằm trong nhóm đồng thuận
- transition quan trọng: `3/4`
  - bắt đầu ván
  - kết thúc ván
  - phát hiện tới lượt mình

## In scope

- normalize card encoding về `3S`, `10D`, `AH`, `2H`
- parse combo đang cần chặn
- attach confidence + frame timestamp
- policy regular/transition consensus

## Out of scope

- action thật
- retry ADB

## Child issues gợi ý

1. Normalize card outputs sang contract mới.
2. Parse `last_played_combo` và `player_card_counts`.
3. Cập nhật validator/consensus theo `2/3` và `3/4`.
4. Gắn `frame_ts` + `confidence` vào state.

## Acceptance criteria

- [x] `TableState` có đủ các field bắt buộc đã chốt.
- [x] Card encoding luôn ở format rank+suit string chuẩn.
- [x] `player_card_counts` được validate trong `[0, 13]`.
- [x] Regular consensus là `2/3` và frame cuối phải thuộc nhóm đồng thuận.
- [x] Transition consensus là `3/4`.
- [x] State cũ hoặc confidence thấp có thể bị worker loại bỏ.

## Trạng thái triển khai

- `TableStateAssembler` và `TableStateConsensus` đã được nối vào typed path của `BotWorker`.
- Decision adapter đã thống nhất encoding rank+suit và vẫn nhận encoding legacy tại boundary.
- Chưa production-ready vì card/button/OCR perception thật chưa cấp đủ `PerceptionSnapshot` cho runtime.

## Dependency

- phụ thuộc `EPIC_01`
- hưởng lợi trực tiếp từ `EPIC_02A` và `EPIC_02B`

## Giao việc phù hợp cho agent

- agent state extraction
- agent validation/consensus
