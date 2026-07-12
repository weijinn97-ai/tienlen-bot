# Epic 02A - Data Bootstrap Automation

## Mục tiêu

Giải bài toán gà-trứng dữ liệu bằng cách thu ảnh nhanh từ bàn thật, offline, chơi với máy hoặc replay nếu game hỗ trợ.

## Ý tưởng chốt

Script automation chỉ cần:

1. join bàn hoặc vào mode offline/replay
2. chờ chia bài
3. screenshot
4. fold hoặc pass
5. lặp lại

Mỗi ván thấy 13 lá. Khoảng `80-100` ván có thể phủ đủ `52` lá với mật độ tốt để bootstrap perception.

## Kết quả cần có

- tool automation thu ảnh lặp
- quy tắc lưu batch rõ ràng vào `data/submissions/<batch>/raw`
- metadata tối thiểu đi vào `manifest.csv`
- pipeline update `08_Image_Index`

## In scope

- auto loop thu ảnh
- hỗ trợ nhiều nguồn: bàn thật, offline, replay
- lưu batch raw dùng chung
- update manifest/index

## Out of scope

- training model hoàn chỉnh
- parse full game state từ ảnh

## Child issues gợi ý

1. Viết loop automation join -> wait -> screenshot -> fold/pass.
2. Hỗ trợ multiple sources: live room, offline, replay nếu có.
3. Tự động import ảnh vào `data/submissions` và export index.

## Acceptance criteria

- [ ] Có thể chạy automation nhiều vòng liên tiếp mà không crash.
- [ ] Mỗi ảnh được import vào batch đúng format repo.
- [ ] Có `manifest.csv` và `README.md` cho batch.
- [ ] `py -3 tools/export_image_index_csv.py` phản ánh batch mới.
- [ ] Có thể thu ít nhất một batch đủ lớn để seed labeling lane.

## Dependency

- nên dùng contract batch hiện có trong `tools/import_user_screenshots.py`
- không chờ full card perception

## Giao việc phù hợp cho agent

- agent thiên automation/tooling
- agent data pipeline
