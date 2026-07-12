# Epic 02B - Turn Owner and UI Signals

## Mục tiêu

Tách `turn_owner` khỏi perception lá bài để lane action/decision có tín hiệu lượt chơi sớm hơn.

## Ý tưởng chốt

Phương án hybrid:

- tín hiệu chính: vòng timer hoặc highlight quanh avatar
- ROI cố định theo 4 vị trí avatar
- classifier nhị phân nhẹ hoặc color mask cực nhẹ
- tín hiệu phụ: delta số bài các cửa giữa 2 frame
- chỉ chốt `turn_owner` khi hai tín hiệu khớp nhau

## Kết quả cần có

- ROI spec cho 4 vị trí avatar
- signal extractor cho timer/highlight
- cross-check bằng `player_card_counts` delta
- output `turn_owner` + `TurnOwnerEvidence`

## In scope

- turn owner
- buttons cơ bản
- game_phase mức coarse
- confidence của tín hiệu

## Out of scope

- detect từng lá bài full fidelity
- decision engine

## Child issues gợi ý

1. Định nghĩa ROI avatar 4 vị trí.
2. Viết detector cho timer/highlight.
3. Viết cross-check delta card counts.
4. Serialize evidence vào `TurnOwnerEvidence`.

## Acceptance criteria

- [x] Có ROI spec cố định cho 4 avatar positions.
- [x] Tín hiệu chính trả được binary/score ổn định trên sample frames.
- [x] Có cross-check delta card counts giữa 2 frame.
- [x] Chỉ set `turn_owner` khi `signals_agree=True`.
- [x] `turn_owner` và `game_phase` đi được vào snapshot/state contract.

## Trạng thái triển khai

- Core detector và sample-frame tests: hoàn tất trong `bot/perception/turn_owner.py`.
- Hiệu chỉnh live theo MEmu/runtime: chưa production-ready, vẫn cần chạy soak test trực tiếp.

## Dependency

- có thể chạy song song với `EPIC_02A`
- cần capture lane đủ để lấy frame ROI ổn định

## Giao việc phù hợp cho agent

- agent nhẹ về CV/classifier
- agent state/perception boundary
