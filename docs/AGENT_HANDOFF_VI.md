# Agent Handoff

Cập nhật: 2026-06-25

Tài liệu này là bản handoff ngắn gọn để agent khác vào repo có thể nắm bối cảnh nhanh, biết phần nào đã xong, phần nào đang làm, và nên bắt đầu từ đâu.

## Mục tiêu dự án

Chúng ta đang xây bot Tiến Lên chạy trên MEmu theo các nguyên tắc:

- một bot gắn với đúng một giả lập
- không map theo vị trí cửa sổ
- capture là Windows-side, không dùng `adb screencap` trong hot path
- ADB chỉ đi qua broker hoặc lớp điều khiển đã chuẩn hóa
- khi một bot lỗi thì không kéo sập cả cụm

## Trạng thái hiện tại

Hiện tại dự án đã xong tốt phần khung vận hành:

- scan và bind đúng giả lập MEmu
- launcher để chọn instance, start hoặc stop bot, xem log
- watchdog và logging ưu tiên `title`
- validation cơ bản và multi-frame consensus scaffold
- ADB broker, supervisor, worker, inference scaffold

Chưa xong phần bot chơi thật:

- live capture production backend
- perception YOLO hoặc OCR thật
- state extraction thật từ màn hình game
- action execution thật trên bàn chơi
- post-action verification
- decision engine Tiến Lên thật

## Các nhánh công việc đang active

### 1. Runtime và launcher

- `M1.5`: làm log dễ đọc hơn
- `M1.6`: graceful stop để stop sạch hơn
- `M5.1`: lưu cấu hình người dùng và instance đã chọn

### 2. Capture đến action

- `M2.1`: live preview và capture backend thật
- `M2.2`: validator thực hơn cho snapshot game
- `M2.3`: perception pipeline
- `M2.4`: parse state game
- `M3.2`: action executor thật
- `M3.3`: xác nhận sau thao tác

### 3. Agent và cấu hình

- `M3.0`: Free API Agent đã đọc token từ env, có validate config rõ và fallback local
- local mode vẫn là mặc định an toàn
- chưa test provider API thật và chưa map payload/parser theo từng provider cụ thể

### 4. Phối hợp nhiều agent và dữ liệu ảnh

- `M0.1`: tracker Google Sheet đã được chuẩn hóa lại
- `M2.0`: có intake ảnh vào `data/submissions/<batch>/raw`
- `08_Image_Index` đã dùng để đồng bộ danh sách ảnh thô cho nhiều agent review hoặc label song song

## Việc nên làm tiếp theo

Thứ tự khuyến nghị:

1. hoàn thiện `graceful stop`
2. thêm live preview capture trong launcher
3. nối perception pipeline thật
4. parse state game thật
5. làm action execution thật
6. thêm post-action verification
7. map Free API Agent theo provider thật nếu muốn dùng API mode

## Những quyết định quan trọng cần giữ

- một bot bằng một worker hoặc process độc lập
- định danh chính là `title`, `vm_index`, `pid`, `hwnd`, `adb_serial`
- không map bot theo window order hoặc screen position
- queue frame nên bounded và latest-only
- nếu state chưa chắc thì không hành động mù

## Tài liệu nên đọc trước

Đọc theo thứ tự này:

1. `docs/PROJECT_BOARD_VI.md`
2. `docs/GOOGLE_SHEET_TRACKER_VI.md`
3. `docs/MULTI_BOT_ARCHITECTURE.md`
4. `docs/google_sheet_seed/00_Overview.csv`
5. `docs/google_sheet_seed/06_Build_Plan.csv`
6. `docs/google_sheet_seed/07_Runtime_Flow.csv`

## Google Sheet chung

Link chung:

`https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0`

Các tab quan trọng:

- `00_Overview`
- `01_Task_Board`
- `02_Agent_Notes`
- `04_Daily_Status`
- `05_Decisions`
- `06_Build_Plan`
- `07_Runtime_Flow`
- `08_Image_Index`

Lưu ý:

- script seed sẽ ghi đè các tab chuẩn
- trước khi sửa lớn nên thêm note vào sheet

## Quy trình ảnh dùng chung

Nếu ảnh đến từ user hoặc nguồn review thủ công, đi theo flow này:

1. import vào batch:

```bash
py -3 tools/import_user_screenshots.py --batch-name your_batch_name --files "C:\path\shot1.png"
```

2. cập nhật `manifest.csv`
3. export lại image index:

```bash
py -3 tools/export_image_index_csv.py
```

4. chỉ đưa ảnh sang `train|val|test` sau khi đã review hoặc label rõ

## Cấu hình API agent

Nếu dùng API mode:

```powershell
$env:TIENLEN_USE_LOCAL_AGENT = "false"
$env:TIENLEN_FREE_API_KEY = "your-real-token"
$env:TIENLEN_FREE_API_ENDPOINT = "https://your-provider.example/v1/completions"
$env:TIENLEN_FREE_API_MODEL = "gpt-nano-free"
```

Hiện trạng:

- local mode là mặc định
- thiếu config thì API agent báo lỗi rõ và fallback local nếu bật fallback
- chưa có adapter chuẩn cho từng provider thực tế

## Validation gần nhất

Đã chạy xanh các kiểm tra sau trong local:

```bash
py -3 -m unittest tests.test_google_sheet_seed_public tests.test_image_index_export tests.test_free_api_agent -v
py -3 -m unittest discover -s tests -v
```

## Ghi chú ngắn cho agent mới

- đừng mô tả dự án như bot chơi hoàn chỉnh
- hiện tại đây vẫn là khung vận hành + một số nhánh đang chuẩn bị cho gameplay thật
- nếu muốn làm nhanh và ít đụng nhau, hãy chọn một lane rõ: `launcher`, `capture`, `perception/state`, `action`, hoặc `supervisor/resource`
