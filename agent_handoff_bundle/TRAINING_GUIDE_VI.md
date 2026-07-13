# Hướng dẫn train perception cho Tiến Lên Bot

Cập nhật: 2026-07-13

Tài liệu này dùng để giao việc train ảnh cho agent Gemini/Copilot trên VPS. Mục tiêu là tạo model có số liệu kiểm chứng được, không chỉ tạo ra file `best.pt`.

## 1. Phạm vi và nguyên tắc khóa

- Không sửa code runtime trong khi chuẩn bị dữ liệu hoặc train.
- Không sửa, crop đè, đổi tên hoặc xóa ảnh gốc trong `data/inbox/user_training_images/raw/`.
- Không dùng weight YOLO bootstrap cũ: lần thử 15 epoch có `mAP50=0` và đã bị loại.
- Không dùng `configs/dataset.yaml` hiện tại: đây là cấu hình cũ, tên và thứ tự lớp không khớp contract runtime.
- Không dùng pseudo bbox từ `tools/build_bootstrap_yolo_dataset.py` làm ground truth production.
- Không trộn nút UI vào model bài. Runtime card model bắt buộc có đúng 52 lớp duy nhất.
- Không đánh giá bằng ảnh hoặc frame gần giống ảnh train.
- Không đưa model vào thao tác thật chỉ vì mAP cao. Phải qua đầy đủ cổng offline, replay, soak read-only và action có giám sát.

Nguồn ảnh người dùng:

```text
data/inbox/user_training_images/raw/
  fullscreen/   # screenshot 1280x720 đầy đủ, ưu tiên cao nhất
  my_hand/      # crop vùng bài trên tay
  table_plays/  # crop vùng bài vừa đánh giữa bàn
  buttons_ui/   # crop nút và trạng thái UI
```

## 2. Kiến trúc train được chốt

Train độc lập trước, chỉ thử model gộp sau khi hai baseline độc lập đã đạt:

1. `hand_cards`: YOLO detection 52 lớp cho bài trên tay, gồm cả lá đang được chọn/nhô lên.
2. `table_cards`: YOLO detection 52 lớp cho bài vừa đánh giữa bàn.
3. `buttons_ui`: ưu tiên template matching hoặc classifier trên ROI cố định. Chỉ dùng YOLO riêng nếu UI có nhiều layout/theme; tuyệt đối không thêm lớp nút vào card model.
4. `ocr_fields`: OCR riêng cho trường chữ/số cần thiết. Không dùng OCR thay YOLO để đọc mã lá bài.
5. `unified_cards`: thí nghiệm tùy chọn sau cùng, trộn hand và table nhưng vẫn đúng 52 lớp; chỉ nhận nếu thắng cả hai model chuyên biệt trên cùng test set và không tăng latency quá mức.

Lý do tách `hand_cards` và `table_cards`: bài trên tay lớn, xòe và che nhau; bài giữa bàn nhỏ hơn, có animation, góc/scale và kiểu chồng khác. Một mAP tổng có thể che việc model rất tốt ở hand nhưng hỏng hoàn toàn ở table.

## 3. Taxonomy 52 lớp bắt buộc

Card code: `S` = Bích, `C` = Chuồn, `D` = Rô, `H` = Cơ.

Thứ tự class ID phải chính xác:

```text
0:3S  1:3C  2:3D  3:3H
4:4S  5:4C  6:4D  7:4H
8:5S  9:5C  10:5D 11:5H
12:6S 13:6C 14:6D 15:6H
16:7S 17:7C 18:7D 19:7H
20:8S 21:8C 22:8D 23:8H
24:9S 25:9C 26:9D 27:9H
28:10S 29:10C 30:10D 31:10H
32:JS 33:JC 34:JD 35:JH
36:QS 37:QC 38:QD 39:QH
40:KS 41:KC 42:KD 43:KH
44:AS 45:AC 46:AD 47:AH
48:2S 49:2C 50:2D 51:2H
```

Danh sách YAML:

```yaml
names: [3S, 3C, 3D, 3H, 4S, 4C, 4D, 4H, 5S, 5C, 5D, 5H, 6S, 6C, 6D, 6H, 7S, 7C, 7D, 7H, 8S, 8C, 8D, 8H, 9S, 9C, 9D, 9H, 10S, 10C, 10D, 10H, JS, JC, JD, JH, QS, QC, QD, QH, KS, KC, KD, KH, AS, AC, AD, AH, 2S, 2C, 2D, 2H]
```

Trước khi nhận artifact, phải load `best.pt` bằng `bot/perception/yolo_cards.py`. Guard runtime phải chấp nhận đủ 52 tên lớp, không trùng và không thiếu.

## 4. Kiểm kê dữ liệu trước khi label

Agent dữ liệu chỉ làm kiểm kê ở vòng đầu, chưa train:

1. Đếm ảnh theo bốn thư mục nguồn.
2. Ghi định dạng, chiều rộng, chiều cao, tỷ lệ khung hình và dung lượng.
3. Tính SHA-256 để tìm file trùng tuyệt đối.
4. Tính perceptual hash để nhóm frame gần giống hoặc frame liên tiếp.
5. Gán `session_id`, `match_id`, `round_id`, `source_zone` nếu xác định được.
6. Xuất `inventory.csv` và báo số ảnh usable/unreadable/duplicate theo zone.
7. Không xóa duplicate; chỉ đánh dấu `duplicate_of`.

Các frame trong cùng burst, cùng ván hoặc gần giống nhau phải vào cùng một split. Không random từng ảnh vì sẽ gây leakage và mAP giả cao.

## 5. Quy tắc bbox

### Bài trên tay (`MY_HAND`)

- Mỗi lá đọc được là một bbox và một class card code.
- Bbox ôm phần lá thực sự nhìn thấy, không đoán phần bị lá khác che.
- Phải chứa đủ ký hiệu rank và suit để con người xác nhận label.
- Giữ quy tắc box nhất quán trên toàn bộ dataset; không lúc box cả lá, lúc chỉ box ký hiệu.
- Lá cuối cùng dù lộ toàn bộ vẫn annotate theo cùng quy tắc phần nhận dạng đã chọn cho hand dataset.
- Lá nhô lên do được chọn vẫn dùng class card code cũ. Trạng thái `SELECTED` ghi trong metadata, không tạo thêm 52 lớp selected.
- Nếu rank hoặc suit bị che, mờ hoặc animation làm con người không chắc chắn thì đánh dấu `ignore`, không ép label.
- Không annotate mặt lưng bài của đối thủ như một card code.

### Bài giữa bàn (`TABLE_PLAY`)

- Dùng dataset riêng với quy tắc bbox riêng nhưng nhất quán trong zone này.
- Annotate từng lá trong combo, không annotate cả combo thành một box.
- Bbox chỉ ôm phần thực tế nhìn thấy; không suy đoán biên bị che.
- Giữ cả ví dụ một lá, đôi, sám, sảnh, tứ quý và nhiều hướng chồng bài.
- Loại frame đang animation mạnh khỏi ground truth chính; có thể giữ làm hard/negative set.
- Nếu bài cũ đang mờ dần và bài mới cùng tồn tại, metadata phải chỉ rõ `active_combo`; không để hai thời điểm thành một nhãn mơ hồ.

### Nút UI

- Tối thiểu phân biệt `play_enabled`, `play_disabled`, `pass_enabled`; bổ sung `pass_disabled`, `ready`, `start` nếu game thực tế có dùng.
- Ảnh không có nút, popup che nút, animation và màn hình ngoài bàn là negative samples quan trọng.
- Sai `play_disabled -> play_enabled` là lỗi an toàn nghiêm trọng hơn bỏ sót nút.

### QA annotation

- 100% ảnh val/test phải được người thứ hai review.
- Tối thiểu 20% ảnh train được review chéo.
- Tool kiểm tra phải từ chối class ID ngoài `0..51`, box ra ngoài ảnh, box rỗng, label thiếu ảnh và ảnh thiếu label.
- Review đặc biệt các cặp dễ nhầm: `S/C`, `D/H`, `6/9`, `10/J`, và card đỏ khi hiệu ứng màu thay đổi.

## 6. Định mức dữ liệu

Mức bootstrap chỉ để tìm lỗi pipeline, không được gọi production:

- Mỗi class/zone có ít nhất 30 instance train, 8 val và 8 test.
- Mọi class đều xuất hiện trong cả ba split.

Mức candidate nên đạt trước khi tốn GPU cho nhiều experiment:

- `hand_cards`: mỗi class ít nhất 150 train, 30 val, 30 test.
- `table_cards`: mỗi class ít nhất 80 train, 20 val, 20 test.
- `buttons_ui`: mỗi trạng thái ít nhất 300 train, 75 val, 75 test; thêm ít nhất 500/100/100 negative frame.
- Test lấy từ session/ván khác train và nên có ít nhất một batch thu ở ngày khác.

Số lượng không thay thế độ đa dạng. Cần phủ:

- hand count từ 13 xuống 1 và nhiều vị trí slot;
- selected/unselected, lượt mình/không phải lượt mình;
- combo table từ 1 đến nhiều lá;
- nền bàn, avatar, popup, chat, hiệu ứng và độ sáng khác nhau;
- ít nhất các biến thể render thực tế sẽ chạy trên MEmu;
- frame sạch, frame nén, frame hơi mờ và hard negatives.

## 7. Cấu trúc dataset trên VPS

Không ghi dữ liệu sinh ra vào thư mục raw. Tạo workspace ngoài repo hoặc volume riêng:

```text
training_workspace/
  hand_cards/
    images/train images/val images/test
    labels/train labels/val labels/test
    dataset.yaml
  table_cards/
    images/train images/val images/test
    labels/train labels/val labels/test
    dataset.yaml
  buttons_ui/
  ocr_fields/
  manifests/
    inventory.csv
    split_manifest.csv
    annotation_review.csv
```

Ví dụ `dataset.yaml` cho từng card model:

```yaml
path: /absolute/path/to/training_workspace/hand_cards
train: images/train
val: images/val
test: images/test
names: [3S, 3C, 3D, 3H, 4S, 4C, 4D, 4H, 5S, 5C, 5D, 5H, 6S, 6C, 6D, 6H, 7S, 7C, 7D, 7H, 8S, 8C, 8D, 8H, 9S, 9C, 9D, 9H, 10S, 10C, 10D, 10H, JS, JC, JD, JH, QS, QC, QD, QH, KS, KC, KD, KH, AS, AC, AD, AH, 2S, 2C, 2D, 2H]
```

`split_manifest.csv` tối thiểu có:

```text
image_path,zone,session_id,match_id,round_id,split,sha256,phash,label_status,reviewer,notes
```

## 8. Chuẩn bị VPS

Ví dụ Linux + NVIDIA GPU:

```bash
git clone https://github.com/weijinn97-ai/tienlen-bot.git
cd tienlen-bot
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install ultralytics opencv-python-headless
nvidia-smi
python -c "import torch, ultralytics; print(torch.__version__, torch.cuda.is_available(), ultralytics.__version__)"
yolo checks
```

Nếu `torch.cuda.is_available()` là `False`, dừng và sửa môi trường CUDA trước; không âm thầm train CPU. Agent phải lưu output `nvidia-smi`, phiên bản Python, PyTorch, CUDA, Ultralytics và `pip freeze` vào báo cáo.

## 9. Train baseline

Chạy một seed trước để xác nhận dữ liệu. Không chạy grid search khi annotation chưa qua QA.

```bash
yolo detect train \
  model=yolo11n.pt \
  data=/absolute/path/to/training_workspace/hand_cards/dataset.yaml \
  imgsz=1280 epochs=150 patience=25 batch=-1 device=0 workers=8 \
  optimizer=AdamW cos_lr=True close_mosaic=10 seed=17 deterministic=True \
  project=runs/cards name=hand_y11n_seed17
```

```bash
yolo detect train \
  model=yolo11n.pt \
  data=/absolute/path/to/training_workspace/table_cards/dataset.yaml \
  imgsz=1280 epochs=150 patience=25 batch=-1 device=0 workers=8 \
  optimizer=AdamW cos_lr=True close_mosaic=10 seed=17 deterministic=True \
  project=runs/cards name=table_y11n_seed17
```

Ghi chú:

- `imgsz=1280` là baseline vì viewport thực tế là `1280x720` và ký hiệu table card khá nhỏ.
- Nếu hết VRAM, giảm batch trước; chỉ giảm `imgsz` sau khi báo benchmark mất recall ở card nhỏ.
- Không augment val/test. Augmentation chỉ nằm trong train pipeline.
- Không dùng flip dọc. Flip ngang chỉ dùng nếu không tạo layout phi thực tế; ưu tiên scale, brightness, blur/nén nhẹ và occlusion nhỏ.
- Không chuyển lên `yolo11s` hoặc model lớn hơn cho đến khi `yolo11n` đã chứng minh lỗi do capacity thay vì label/data.
- Sau baseline đạt candidate gate, chạy thêm seed `41` và `73`; báo mean và độ lệch, không chỉ chọn run may mắn nhất.

## 10. Đánh giá bắt buộc

Validation trong lúc train dùng `val`. Locked test chỉ chạy khi đã chốt model/hyperparameter:

```bash
yolo detect val \
  model=runs/cards/hand_y11n_seed17/weights/best.pt \
  data=/absolute/path/to/training_workspace/hand_cards/dataset.yaml \
  split=test imgsz=1280 conf=0.65 iou=0.50 device=0 plots=True save_json=True
```

Lặp lại cho table model. Ngoài mAP, agent phải viết evaluator theo state thực tế:

- per-class precision, recall và F1 cho đủ 52 lớp;
- worst 10 classes và confusion matrix;
- false positives trên mỗi frame;
- exact hand set accuracy: frame chỉ pass khi không thiếu, không thừa và không sai lá;
- exact table combo accuracy: toàn bộ bộ giữa bàn phải đúng;
- metric riêng cho selected hand, combo nhiều lá, animation/hard set;
- latency warm-up 50 frame, sau đó đo ít nhất 1000 frame: mean, p50, p95, p99;
- VRAM cao nhất và throughput thực tế.

Không dùng mAP tổng để thay exact-state accuracy. Bot chỉ cần sai một lá là decision engine có thể chọn hành động sai.

## 11. Cổng nghiệm thu

### Candidate offline

- Card model có đúng 52 class theo đúng thứ tự contract.
- `mAP50 >= 0.98` và `mAP50-95 >= 0.75` trên locked test.
- `hand_cards`: precision/recall tổng `>= 0.99`, exact hand set `>= 98%`, recall class thấp nhất `>= 95%`.
- `table_cards`: precision/recall tổng `>= 0.98`, exact combo `>= 97%`, recall class thấp nhất `>= 92%`.
- Không class nào vắng ở train/val/test.
- Không phát hiện leakage theo SHA-256, pHash, session hoặc round.
- Inference p95 mỗi card model `<= 70 ms` trên GPU đích ở `1280x720`; full perception target `<= 125 ms` để giữ 8 FPS.

Nếu chưa đạt, agent phải trả hard examples và phân loại nguyên nhân `label`, `coverage`, `domain`, `resolution`, `capacity`; không tự tăng epoch vô hạn.

### Button/OCR safety

- Button state exact accuracy `>= 99.5%`.
- Không có false `PLAY enabled` trên tối thiểu 2.000 frame disabled/negative locked test.
- OCR field quan trọng đạt exact field accuracy `>= 99%`; trường confidence thấp phải trả `UNKNOWN`, không đoán.
- UI popup/animation/ngoài bàn không được tạo tín hiệu enabled giả.

### Replay và live

1. Replay toàn bộ locked video/frame sequence với consensus thường `2/3`, frame cuối phải thuộc consensus.
2. Transition bắt đầu/kết thúc ván và tới lượt mình dùng `3/4`.
3. Soak read-only tối thiểu 2 giờ hoặc 20 ván, không tap; lưu mọi mismatch và latency.
4. Action supervised tối thiểu 100 action hợp lệ, mỗi action phải qua selection verify, button-enabled recapture và post-action verify.
5. Yêu cầu `0` tap sai lá, `0` false PLAY, `0` action khi không phải lượt; lỗi timeout phải fail-safe thành WAIT/stop.
6. Chỉ sau các bước trên mới đề xuất production candidate. Không tự bật unattended real-money gameplay.

## 12. Artifact agent phải trả

Mỗi run được đề xuất phải có đầy đủ:

```text
model_card.md
best.pt
best.pt.sha256
dataset.yaml
dataset_stats.csv
split_manifest.csv
annotation_review.csv
train_command.txt
environment.txt
metrics.json
per_class_metrics.csv
latency.csv
confusion_matrix.png
PR_curve.png
hard_examples/
test_predictions/
```

`model_card.md` phải ghi:

- model dùng cho `hand_cards`, `table_cards`, `buttons_ui` hay `ocr_fields`;
- Git commit nguồn, dataset version/hash và ngày train;
- lệnh train đầy đủ, seed, epochs thực chạy và lý do early stop;
- metric val/test, worst classes, exact-state accuracy và latency;
- giới hạn đã biết: resolution, theme, animation, popup, card scale;
- kết luận rõ `REJECTED`, `CANDIDATE` hoặc `READY_FOR_SUPERVISED_LIVE`.

Không commit `*.pt`, `runs/` hoặc raw dataset lớn vào Git. Gửi artifact qua storage/release riêng và luôn kèm SHA-256. Repo chỉ nên nhận script, manifest đã redaction, report và thay đổi tích hợp đã review.

## 13. Phân công agent tiết kiệm chi phí

### Agent 1 - Data/QA (Gemini)

- Chỉ kiểm kê, deduplicate, tạo split theo session và lập báo cáo coverage.
- Tạo/kiểm tra annotation theo quy tắc bbox.
- Xuất dataset version cùng ba manifest.
- Không train và không sửa runtime.

### Agent 2 - Train/Evaluate (Copilot VPS)

- Xác thực taxonomy và dataset trước khi dùng GPU.
- Train `hand_y11n_seed17` và `table_y11n_seed17`.
- Chỉ chạy thêm seed/model khi baseline qua QA và có lý do từ error analysis.
- Xuất toàn bộ artifact ở mục 12.
- Không tự thay weight production.

### Agent 3 - Independent review

- Kiểm tra leakage, 100% label val/test và chạy lại evaluator.
- Load weight qua guard `YoloCardDetector`.
- Xác nhận metric có thể tái lập từ command và artifact.
- Chỉ đề xuất trạng thái, không tự bật live action.

## 14. Mẫu yêu cầu gửi cho agent

```text
Đọc agent_handoff_bundle/TRAINING_GUIDE_VI.md và làm đúng phạm vi vai trò được giao.
Không sửa runtime, không dùng configs/dataset.yaml cũ, không dùng pseudo bbox làm ground truth,
không trộn button vào 52 lớp card và không train trước khi data QA pass.
Đầu tiên hãy trả inventory/coverage/leakage report. Khi được phép train, trả đầy đủ artifact mục 12,
metric theo từng zone và kết luận REJECTED/CANDIDATE/READY_FOR_SUPERVISED_LIVE.
Không được gọi model production chỉ dựa trên best.pt hoặc mAP tổng.
```

## 15. Checklist chủ dự án duyệt

- [ ] Ảnh raw được giữ nguyên và có hash.
- [ ] Hand/table/button/OCR được tách đúng domain.
- [ ] Class ID đúng `3S..2H` theo thứ tự khóa.
- [ ] Bbox đã QA, không có label đoán khi không đọc được.
- [ ] Split theo session/ván, không có duplicate leakage.
- [ ] Mọi class có mặt trong train/val/test.
- [ ] Baseline một seed đã có error analysis.
- [ ] Locked test chưa bị dùng để chỉnh hyperparameter.
- [ ] Exact hand và exact combo đạt cổng, không chỉ mAP.
- [ ] Button không false-enabled trên safety test.
- [ ] Latency đo trên GPU đích đạt yêu cầu.
- [ ] Artifact/model card/checksum đầy đủ.
- [ ] Runtime guard chấp nhận đúng 52 class.
- [ ] Replay và soak read-only đã pass.
- [ ] 100 action supervised pass với verify thật.
- [ ] Chỉ người chủ dự án mới quyết định bật production.
