# Full Project Handoff

Cập nhật: 2026-07-13
Phạm vi: bản Markdown đầy đủ để agent mới có thể nắm kỹ toàn bộ dự án mà không cần tự đi dò nhiều file trước.

---

## 1. Mục tiêu của dự án

Chúng ta đang xây một bot Tiến Lên chạy trên giả lập MEmu trên Windows, với các mục tiêu cốt lõi:

- mỗi bot gắn đúng với đúng một giả lập
- không bị nhầm cửa sổ, nhầm ADB, nhầm identity
- nếu một bot lỗi thì không kéo sập toàn bộ cụm
- người vận hành không chuyên vẫn có thể chọn bot, chạy, dừng, đọc log
- kiến trúc đủ rõ để sau này mở rộng nhiều bot cùng lúc

Dự án hiện **chưa phải bot gameplay hoàn chỉnh**. Nó đang ở trạng thái:

- khung vận hành đã khá tốt
- workflow phối hợp nhiều agent đã có
- perception, state extraction, action thật và decision thật vẫn còn phải làm

---

## 2. Executive Summary

### 2.1. Những gì đã có

- scan và bind đúng giả lập MEmu theo `vm_index`, `title`, `pid`, `hwnd`, `adb_serial`
- launcher để chọn instance, start hoặc stop bot, xem log
- watchdog và logging ưu tiên `title`
- validation cơ bản và multi-frame consensus scaffold
- ADB broker, supervisor, worker, inference scaffold
- Google Sheet tracker đã seed chuẩn
- workflow intake ảnh dùng chung cho nhiều agent
- `Free API Agent` đã đọc token từ biến môi trường thay vì hardcode

### 2.2. Những gì chưa xong

- live preview capture production trong launcher
- pipeline perception YOLO/OCR thật
- parse state game thật từ frame
- action execution thật và post-action verification
- decision engine Tiến Lên thật
- multi-bot end-to-end thật trên gameplay loop hoàn chỉnh

### 2.3. Snapshot task nhanh

- `4` task `Đã xong`
- `8` task `Đang làm`
- `9` task `Làm tiếp`
- `12` task ưu tiên `Cao`
- `30` ảnh đang ở shared intake, tất cả đang `needs_bbox_label`

---

## 3. Trạng thái GitHub và local hiện tại

### 3.1. GitHub

Remote `origin`:

- `https://github.com/weijinn97-ai/tienlen-bot.git`

Branch hiện tại:

- `main`

Tại thời điểm cập nhật file này:

- `origin/main` đã bao gồm batch handoff mới nhất
- batch đó có `contracts/`, `docs/epics/`, issue template, contract tests, checklist và dashboard HTML
- agent khác có thể vào GitHub để thấy đúng bức tranh handoff hiện tại

Nếu cần xem 5 commit gần nhất:

- mở `agent_handoff_bundle/RECENT_COMMITS.txt`
- hoặc chạy `git log --oneline --decorate -5`

### 3.2. Local

Bundle local hiện có đầy đủ các file để handoff nhanh:

- `agent_handoff_bundle/WORK_COMPLETION_CHECKLIST_VI.md`
- `agent_handoff_bundle/FULL_PROJECT_HANDOFF_VI.md`
- `agent_handoff_bundle/index.html`
- `agent_handoff_bundle/LOCAL_GIT_STATUS.txt`
- `agent_handoff_bundle/RECENT_COMMITS.txt`

Lưu ý:

- `LOCAL_GIT_STATUS.txt` và `RECENT_COMMITS.txt` là snapshot phục vụ handoff
- nếu cần trạng thái thật ngay lúc mở repo, ưu tiên chạy `git status -sb`

---

## 4. Nguyên tắc kiến trúc không được phá

Đây là các rule gần như bất di bất dịch của dự án:

- một bot bằng một worker hoặc process độc lập
- không map bot theo vị trí cửa sổ hoặc thứ tự window
- định danh chính phải dựa trên `title`, `vm_index`, `pid`, `hwnd`, `adb_serial`
- capture là Windows-side, không dùng `adb screencap` trong hot path
- ADB phải đi qua broker hoặc lớp điều khiển đã chuẩn hóa
- frame queue bounded và latest-only
- validation và multi-frame consensus quan trọng hơn FPS cao
- nếu state chưa chắc, bot không được hành động mù
- recovery nên pause/restart bot lỗi riêng lẻ, không reset cả cụm

---

## 5. Bản đồ repo

Các khu vực chính trong repo:

- `bot/runtime/`
  - schema, supervisor, worker, validation
- `bot/actions/`
  - ADB broker, controller, action path
- `bot/capture/`
  - capture scaffold theo cửa sổ Windows
- `bot/inference/`
  - inference service scaffold
- `bot/agent/`
  - local agent, free API agent, orchestrator, state adapter
- `bot/ui/`
  - launcher app cho operator
- `docs/`
  - kiến trúc, setup, board, tracker guide
- `docs/google_sheet_seed/`
  - seed CSV cho các tab Google Sheet
- `data/submissions/`
  - shared intake ảnh thô trước khi label/train
- `tools/`
  - seed sheet, import ảnh, export image index, launcher, scanner
- `tests/`
  - parser tests, validation tests, supervisor tests, agent config tests, image index export tests

Các file nên đọc trước nếu mới vào:

1. `agent_handoff_bundle/README.md`
2. `agent_handoff_bundle/docs/AGENT_HANDOFF_VI.md`
3. `agent_handoff_bundle/docs/PROJECT_BOARD_VI.md`
4. `agent_handoff_bundle/docs/MULTI_BOT_ARCHITECTURE.md`
5. `agent_handoff_bundle/tracker/00_Overview.csv`
6. `agent_handoff_bundle/tracker/01_Task_Board.csv`
7. `agent_handoff_bundle/tracker/06_Build_Plan.csv`
8. `agent_handoff_bundle/tracker/07_Runtime_Flow.csv`
9. `agent_handoff_bundle/tracker/08_Image_Index.csv`

---

## 6. Thành phần chính của hệ thống

### 6.1. Discovery và binding

Mục tiêu:

- quét các instance MEmu đang chạy
- map đúng `vm_index`, `title`, `pid`, `hwnd`, `adb_serial`, `android_serial`
- không cho start bot nếu binding còn mơ hồ

Ý nghĩa:

- identity correctness quan trọng hơn tốc độ
- đây là nền của toàn bộ multi-bot

### 6.2. Launcher

Đã có:

- chọn đúng giả lập theo title
- start/stop bot session
- log realtime
- copy binding stub

Chưa có:

- graceful stop sạch
- live preview frame
- lưu profile hoặc cấu hình đã chọn

### 6.3. Runtime supervisor/worker

Đã có:

- worker per bot
- schema cho frame envelope
- validation scaffold
- circuit-breaker-oriented mindset

Chưa có:

- full gameplay loop production
- multi-bot session thật trên end-to-end path

### 6.4. Capture

Đã có:

- capture scaffold theo `HWND`

Chưa có:

- backend production cuối cùng để preview/live frame ổn định
- identity recheck từ image fingerprint

### 6.5. Perception

Đã có:

- inference service scaffold
- turn-owner core dùng ROI chuẩn hóa, color mask vòng vàng và card-count delta
- test nhận đúng 4 vị trí lượt chơi trên sample frames thật `1.png` đến `4.png`

Chưa có:

- detect card/button/text từ frame thật
- OCR/YOLO contract ổn định cho bot_id + frame_id
- runtime integration và soak test turn-owner trên MEmu live

### 6.6. State extraction

Đã có:

- typed path `PerceptionSnapshot -> TableState -> consensus -> DecisionOrchestrator`
- regular consensus `2/3`, transition consensus `3/4`, latest-frame bắt buộc thuộc nhóm
- lọc state cũ hoặc confidence thấp
- adapter hỗ trợ encoding chuẩn và legacy tại boundary

Chưa có:

- parse card/button/text thật từ detection/OCR
- runtime soak test với snapshot thật liên tục

### 6.7. Decision

Đã có:

- local agent placeholder
- free API agent with env config and safe fallback behavior

Chưa có:

- decision engine Tiến Lên đúng luật và hợp lý
- provider-specific adapter cho API mode thật

### 6.8. Action

Đã có:

- action executor scaffold
- ADB broker serialization

Chưa có:

- map tọa độ bài và nút bấm thật
- xác nhận sau thao tác bằng ảnh

---

## 7. Task board chi tiết

### 7.1. Đã xong

| Mã | Hạng mục | Ý nghĩa |
|---|---|---|
| `M1.1` | Khung chạy bot | Có supervisor, worker, frame schema, validation, ADB broker, inference scaffold |
| `M1.2` | Dọn hot path ADB | ADB không còn dùng để chụp ảnh trong hot path |
| `M1.3` | Quét đúng giả lập MEmu | Map được identity chuẩn cho từng instance |
| `M1.4` | Launcher cho người vận hành | Có UI để chọn instance và theo dõi log |

### 7.2. Đang làm

| Mã | Hạng mục | Trạng thái |
|---|---|---|
| `M1.5` | Log dễ đọc hơn | Đã ưu tiên title thay vì IP, còn thiếu màu/lọc/lưu |
| `M1.6` | Graceful stop | Đã có stop, còn phải dừng mềm hơn |
| `M2.0` | Intake ảnh và image index dùng chung | Đã có workflow raw batch + manifest + export index |
| `M2.2` | Validation snapshot | Đã có validator cơ bản, còn thiếu rule game thật |
| `M3.0` | Free API Agent an toàn | Env config + lazy init + fallback local + tests đã có |
| `M4.2` | Quản lý tài nguyên máy | Có monitor và limit cơ bản |
| `M5.2` | Test đầy đủ hơn | Đã có thêm tests cho agent config và image index |
| `M0.1` | Chuẩn hóa sheet phối hợp agent | Tracker đã seed chuẩn, vẫn phải cập nhật đều |

### 7.3. Làm tiếp

| Mã | Hạng mục | Ghi chú |
|---|---|---|
| `M2.1` | Capture production + live preview | Một trong các bước ưu tiên nhất |
| `M2.3` | Perception pipeline | Nối YOLO/OCR thật |
| `M2.4` | State extraction thật | Parse game state từ detection/OCR |
| `M3.1` | Decision engine thật | Luật hoặc policy Tiến Lên |
| `M3.2` | Action execution thật | Map tọa độ và thao tác thật |
| `M3.3` | Post-action verification | Bắt buộc để tránh bấm mù |
| `M4.1` | Multi-bot supervision thật | Sau single-bot end-to-end |
| `M4.3` | Recovery rõ chính sách | Pause/restart riêng bot lỗi |
| `M5.1` | Lưu cấu hình người dùng | Nhớ instance và profile |

---

## 8. Build plan end-to-end

Đây là logic tuyến tính lớn của dự án:

### P0. Foundation và coordination

- `BP0`: khóa nguyên tắc, rule nhiều agent, tracker
- `BP0A`: sheet handoff và coordination để agent mới vào là hiểu trạng thái ngay

### P1. Operator-ready runtime

- `BP1`: launcher vận hành tốt
- `BP1A`: cấu hình Free API Agent an toàn
- `BP2`: lưu cấu hình user

### P2. Reliable visual input

- `BP3`: capture production backend
- `BP3A`: shared screenshot intake
- `BP4`: identity recheck trên ảnh

### P3. Understanding game state

- `BP5`: perception pipeline
- `BP6`: state extraction
- `BP7`: validator + consensus

### P4. Taking actions safely

- `BP8`: action execution thật
- `BP9`: post-action verification

### P5. Real gameplay

- `BP10`: decision engine Tien Len
- `BP11`: single-bot end-to-end

### P6. Multi-bot and resilience

- `BP12`: multi-bot supervision
- `BP13`: resource control và recovery

### P7. Hardening

- `BP14`: test, docs, preset, release nội bộ

### Dependency logic ngắn gọn

Thứ tự ít gây làm lại nhất:

1. launcher stop sạch
2. capture production + preview
3. perception
4. state extraction
5. action execution
6. post-action verification
7. decision engine
8. multi-bot end-to-end

---

## 9. Runtime flow thật sự của bot

Luồng runtime hiện được định nghĩa như sau:

1. `Scan + Bind`
   - launcher gọi discovery
   - chọn đúng instance
   - bind identity rõ ràng

2. `Start Session`
   - launcher gọi supervisor
   - supervisor sinh bot worker riêng

3. `Capture`
   - worker chụp frame đúng cửa sổ `HWND`
   - frame được gắn `bot_id`, `frame_id`, `timestamp`

4. `Identity Check`
   - validator xác nhận vẫn là đúng giả lập hoặc đúng fingerprint

5. `Perception`
   - detect card, button, text từ ROI

6. `State Extraction`
   - parse detection thành state game chuẩn hóa

7. `Consensus`
   - chỉ tin state khi ổn định qua 2-3 frame

8. `Decision`
   - local agent hoặc Free API Agent chọn action
   - local mode là mặc định an toàn

9. `Act`
   - action plan đi qua `AdbBroker`
   - gửi tap/swipe/text đúng serial

10. `Post-Action Verify`
    - capture lại sau action
    - kiểm tra thay đổi mong đợi

11. `Recovery`
    - nếu timeout, drift identity, lỗi ADB hay quá tải
    - pause/restart riêng bot lỗi

Điểm then chốt:

- không được action khi chưa có state ổn định
- không được bấm lặp mù
- phải có verify sau action

---

## 10. Data lane và ảnh dùng chung

### 10.1. Vì sao có `data/submissions/`

Ảnh người dùng gửi hoặc ảnh review thủ công không nên đưa thẳng vào `train/val/test`.  
Chúng cần một hàng chờ chung để:

- giữ provenance rõ
- nhiều agent cùng review được
- phân tách raw intake khỏi training set

### 10.2. Workflow hiện tại

1. import ảnh vào batch:

```bash
py -3 tools/import_user_screenshots.py --batch-name your_batch_name --files "C:\path\shot1.png"
```

2. ảnh được copy vào:

- `data/submissions/<batch>/raw/`
- kèm `manifest.csv`
- kèm `README.md` cho batch

3. export index:

```bash
py -3 tools/export_image_index_csv.py
```

4. index này đi vào:

- `docs/google_sheet_seed/08_Image_Index.csv`
- `agent_handoff_bundle/tracker/08_Image_Index.csv`

5. chỉ sau khi review/label rõ mới chuyển ảnh sang:

- `data/images/train|val|test`
- `data/labels/train|val|test`

### 10.3. Snapshot data hiện tại

- số batch: `1`
- batch hiện có: `2026-06-21_memu_hand_screenshots`
- số ảnh: `30`
- `label_status`: tất cả đang `needs_bbox_label`
- `split_status`: tất cả đang `hand_read`

### 10.4. Lưu ý về dữ liệu

`08_Image_Index.csv` có cột `original_source_path`, nghĩa là có thể chứa đường dẫn local của máy.  
Nếu chia sẻ ra ngoài phạm vi nội bộ thì nên kiểm tra/redact trước.

---

## 11. Agent lane và cách chia việc song song

Hiện tại có thể chia lane như sau:

### Lane A. Launcher / operator / config

Phù hợp cho:

- `M1.5`, `M1.6`, `M5.1`
- polish launcher
- lưu cấu hình đã chọn

### Lane B. Capture / preview / identity

Phù hợp cho:

- `M2.1`
- `BP3`
- `BP4`

### Lane C. Perception / state / validation

Phù hợp cho:

- `M2.2`, `M2.3`, `M2.4`
- `BP5`, `BP6`, `BP7`

### Lane D. Action / post-action verify

Phù hợp cho:

- `M3.2`, `M3.3`
- `BP8`, `BP9`

### Lane E. Supervisor / resource / recovery

Phù hợp cho:

- `M4.1`, `M4.2`, `M4.3`
- `BP12`, `BP13`

### Lane F. Agent config / API adapter

Phù hợp cho:

- `M3.0`
- provider-specific payload/parser
- test thật với endpoint thật

### Lane G. Data / labeling coordination

Phù hợp cho:

- `M2.0`
- import ảnh mới
- cập nhật manifest
- export image index
- chia việc label hoặc review

---

## 12. Free API Agent hiện ở đâu

### 12.1. Đã làm

- token và endpoint được đọc từ env
- local mode là default
- `FreeAPIAgent` chỉ khởi tạo khi thực sự dùng
- cấu hình thiếu sẽ báo lỗi rõ
- có fallback local
- có test unit

### 12.2. Chưa làm

- chưa map payload/parser theo provider thật
- chưa xác nhận compatibility với endpoint production thật

### 12.3. Cách bật API mode

```powershell
$env:TIENLEN_USE_LOCAL_AGENT = "false"
$env:TIENLEN_FREE_API_KEY = "your-real-token"
$env:TIENLEN_FREE_API_ENDPOINT = "https://your-provider.example/v1/completions"
$env:TIENLEN_FREE_API_MODEL = "gpt-nano-free"
```

### 12.4. Kết luận

API lane hiện **an toàn hơn trước** nhưng **chưa production-ready**.

---

## 13. Quyết định quan trọng đã chốt

| ID | Chủ đề | Quyết định |
|---|---|---|
| `D-001` | Kiến trúc bot | Một bot bằng một process độc lập, chia sẻ inference service và ADB broker |
| `D-002` | Định danh giả lập | Ưu tiên title, vm_index, pid, hwnd, adb_serial; không map theo vị trí cửa sổ |
| `D-003` | Cấu hình Free API Agent | Đọc token/endpoint từ env; local mode là mặc định; lazy init khi dùng |
| `D-004` | Intake ảnh dùng chung | Ảnh user vào `data/submissions/<batch>/raw` + manifest trước; export image index trước khi move sang train/val/test |

---

## 14. Google Sheet tracker chung

Link:

- `https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0#gid=0`

Các tab quan trọng:

- `00_Overview`
- `01_Task_Board`
- `02_Agent_Notes`
- `03_Change_Requests`
- `04_Daily_Status`
- `05_Decisions`
- `06_Build_Plan`
- `07_Runtime_Flow`
- `08_Image_Index`

Lưu ý:

- script seed có thể ghi đè các tab chuẩn
- nên đọc `00_Overview` → `06_Build_Plan` → `07_Runtime_Flow` trước khi bắt đầu sửa lớn
- trước khi sửa lớn nên thêm note vào tracker nếu đang phối hợp với nhiều agent

---

## 15. Validation gần nhất

Lần validation gần nhất được ghi nhận trong handoff:

```bash
py -3 -m unittest tests.test_google_sheet_seed_public tests.test_image_index_export tests.test_free_api_agent -v
py -3 -m unittest discover -s tests -v
```

Kết quả đã từng xanh:

- `46` tests

Những nhóm test đã có:

- ADB parser/broker
- runtime validation
- supervisor
- Google Sheet seed helper
- image index export
- turn-owner ROI/highlight/delta/consensus
- typed table-state assembly, freshness và multi-frame consensus
- normalized local decision fallback và typed BotWorker path
- agent config / fallback

Những nhóm test còn yếu/chưa đủ:

- UI smoke test
- capture integration
- action integration
- provider-specific API test
- end-to-end single-bot demo test

---

## 16. Blocker và rủi ro còn mở

### 16.1. Blocker kỹ thuật

- chưa có capture preview production backend
- chưa test provider API thật
- chưa có perception contract thật để lane state/action bám theo

### 16.2. Rủi ro vận hành

- nếu chưa làm graceful stop tốt, operator experience sẽ còn xấu
- nếu chưa có post-action verify, bot rất dễ bấm mù
- nếu perception/state chưa ổn định mà action sớm, nguy cơ hành vi sai rất cao

### 16.3. Rủi ro data

- image index chứa đường dẫn local
- raw screenshot chưa phải training-ready
- nếu nhiều agent cùng chỉnh manifest mà không phối hợp có thể gây lệch metadata

---

## 17. Gợi ý việc làm ngay cho agent mới

Nếu muốn bắt đầu mà ít đụng người khác:

### Option 1. Lane UI/operator

Làm:

- graceful stop
- log filtering
- lưu cấu hình launcher

### Option 2. Lane capture/perception

Làm:

- live preview
- capture backend thật
- perception contract

### Option 3. Lane state/action

Làm:

- parse state game
- map tọa độ action
- verify sau thao tác

### Option 4. Lane data

Làm:

- review `08_Image_Index`
- chuẩn hóa manifest
- chia task labeling

### Option 5. Lane API agent

Làm:

- adapter cho provider cụ thể
- test endpoint thật
- chuẩn hóa parser output

---

## 18. Command hữu ích

### Launcher

```bash
py -3 tools/launch_bot_ui.py
```

### Quét MEmu

```bash
py -3 tools/scan_memu_adb.py
py -3 tools/scan_memu_adb.py --as-bindings
```

### Seed Google Sheet

```bash
py -3 tools/seed_google_sheet_public.py --sheet-url "https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0"
```

### Import ảnh user

```bash
py -3 tools/import_user_screenshots.py --batch-name your_batch_name --files "C:\path\shot1.png"
```

### Export image index

```bash
py -3 tools/export_image_index_csv.py
```

### Chạy test

```bash
py -3 -m unittest discover -s tests -v
```

---

## 19. Kết luận ngắn gọn

Nếu tóm dự án vào một câu:

> Khung vận hành và phối hợp nhiều agent đã khá rõ, nhưng gameplay loop thật của bot vẫn còn phụ thuộc vào 4 mắt xích chưa hoàn chỉnh: capture production, perception/state extraction thật, action có verify, và decision engine thật.

Nếu tóm thứ tự làm:

> stop sạch → preview/capture thật → perception → state → action → verify → decision → multi-bot end-to-end

Nếu tóm điều cần giữ:

> identity correctness quan trọng hơn tốc độ, và bot không được hành động khi state còn mơ hồ.
