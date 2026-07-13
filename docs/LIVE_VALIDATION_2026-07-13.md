# Live Validation - 2026-07-13

## Môi trường

- MEmu VM: `203` (`11JP - 203H AI`)
- HWND: `0x230df2`
- ADB serial: `127.0.0.1:23533`
- Android viewport: `1280x720`

## Capture soak read-only

Lệnh:

```powershell
py -3 tools/run_live_soak.py --hwnd 0x230df2 --duration 30 --fps 8 --viewport 1280x720
```

Kết quả:

- `239` frames trong `30` giây
- mọi frame đúng `1280x720`
- capture + turn signal mean `28.668 ms`, p95 `43.064 ms`, max `46.619 ms`
- `0` errors
- `turn_owner=UNKNOWN` trong lobby là kết quả mong đợi

## ADB action + post-action verify

Smoke test an toàn mở Cài đặt, verify ROI, sau đó tự gửi Back; không vào bàn và không tiêu coin.

Kết quả:

- ADB tap thành công qua serial thật
- ROI diff pass ngay attempt đầu
- mean absolute diff `25.09`
- changed pixel ratio `0.999603`
- reason `roi_change_confirmed`

## Gameplay thật - phòng 302057

Đã chạy hai action hợp lệ bằng ADB trên VM 203:

1. Chặn `6S` bằng `7S`: selection ROI pass, `PLAY` chuyển enabled, action ROI pass, hand `13 -> 12`.
2. Lead `3D`: recognizer đọc đúng 12 lá, selection ROI pass, detector xác nhận `PLAY enabled`, action ROI pass, hand `12 -> 11`.

Fixed-layout card fallback được train template từ batch cũ và giữ riêng frame live để test:

- exact slot recall trên hand 13 và 12: `25/25`
- frame fresh sau action thứ hai đọc đúng toàn bộ 11 lá
- regression test khóa hand count `13/12/11`
- button detector khóa transition `PLAY disabled -> enabled -> disabled`

Hai batch gameplay thật:

- `data/submissions/2026-07-13_live_vm203_gameplay`
- `data/submissions/2026-07-13_live_vm203_gameplay_round2`

## YOLO bootstrap

- Dataset generator tạo `24 train / 6 val / 3 test` từ pseudo boxes.
- YOLO11n 52-class đã train thử 15 epochs nhưng validation `mAP50=0`.
- Weight này bị loại và nằm ngoài runtime/Git.
- Runtime YOLO guard vẫn yêu cầu đúng 52 classes; cần bbox review và thêm dữ liệu trước khi retrain.

## Chưa được gọi là production gameplay

- Chưa có YOLO weight 52 lớp đạt validation.
- Pseudo bbox hiện chỉ dùng bootstrap, chưa thay thế bbox review thủ công.
- Fixed-layout fallback chỉ được bảo đảm cho viewport/game layout `1280x720` hiện tại.
- Chưa có soak dài cả ván với recovery/error injection.

Backend đã có guard để từ chối model sai taxonomy, nhưng không thay thế artifact model và dữ liệu đánh giá thật.
