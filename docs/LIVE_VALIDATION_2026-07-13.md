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

## Chưa được gọi là production gameplay

- Repo chưa có YOLO weight 52 lớp.
- Ảnh hiện có mới có danh sách 13 lá theo frame, chưa có bbox label để train/evaluate.
- Chưa có template nút `PLAY/PASS` lấy từ frame đang chơi thật.
- Chưa chạy soak trong một ván thật vì thao tác vào bàn có thể dùng coin/tài khoản.

Backend đã có guard để từ chối model sai taxonomy, nhưng không thay thế artifact model và dữ liệu đánh giá thật.
