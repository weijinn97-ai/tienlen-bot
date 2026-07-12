# Work Completion Checklist

Cập nhật: 2026-07-12

Mục đích: đây là checklist ngắn gọn nhưng chặt chẽ để agent khác nhìn vào biết ngay phần nào đã thật sự có trong repo local, phần nào mới ở mức scaffold/contract, và phần nào vẫn chưa được coi là hoàn tất.

File này không thay thế cho `FULL_PROJECT_HANDOFF_VI.md`. Nó là bảng kiểm nhanh để tránh hiểu nhầm rằng dự án đã xong end-to-end.

## Legend

- `[x]` Đã có rõ ràng trong repo local và đã được xác nhận.
- `[~]` Đã có scaffold/contract/test một phần, nhưng chưa production-ready.
- `[ ]` Chưa hoàn tất, không nên đánh dấu xong.

## 1. Handoff và phối hợp agent

- [x] Có thư mục bundle riêng để gửi agent khác: `agent_handoff_bundle/`
- [x] Có bản handoff Markdown đầy đủ: `agent_handoff_bundle/FULL_PROJECT_HANDOFF_VI.md`
- [x] Có bản HTML tổng hợp 1 file: `agent_handoff_bundle/index.html`
- [x] Có CSV snapshot của Google Sheet tracker trong `agent_handoff_bundle/tracker/`
- [x] Có issue template cho agent work item: `.github/ISSUE_TEMPLATE/agent_work_item.md`

## 2. Contract và roadmap đã chốt

- [x] Có contract module riêng: `contracts/interfaces.py`
- [x] Encoding lá bài đã chốt ở dạng `"{rank}{suit}"`, ví dụ `3S`, `10D`, `AH`, `2H`
- [x] Thứ tự so sánh đã chốt: rank `3<4<...<K<A<2`, suit `S<C<D<H`
- [x] `TableState` đã bao gồm `my_cards`, `last_played_combo`, `player_card_counts`, `turn_owner`, `buttons`, `game_phase`, `frame_ts`, `confidence`
- [x] `VerifySpec` đã chốt theo hướng A primary, B escalation
- [x] Consensus đã chốt `2/3` cho action thường và `3/4` cho transition quan trọng, có yêu cầu latest-frame
- [x] Roadmap đã được tách thành 5 epic, trong đó Phase 2 tách thành `2A` và `2B`

## 3. Những gì đã thật sự được implement và verify

- [x] `Free API Agent` đọc config từ env, lazy init, có fallback local
- [x] Workflow intake ảnh và export image index đã có tool riêng
- [x] Có test riêng cho contract trong `tests/test_contract_interfaces.py`
- [x] Full test suite local đang xanh: `25` tests pass với `py -3 -m unittest discover -s tests -v`
- [~] Runtime supervisor/validation/multi-bot scaffold đã có nền, nhưng chưa phải gameplay loop production hoàn chỉnh
- [~] Image intake lane đã sẵn để phối hợp nhiều agent, nhưng dữ liệu hiện tại vẫn chưa phải train set hoàn chỉnh

## 4. Những gì chưa được phép coi là hoàn tất

- [ ] Capture production backend và live preview ổn định
- [ ] Perception YOLO/OCR thật cho bài, nút và text
- [ ] Turn owner detector hybrid chạy trên frame thật
- [ ] State extraction thật từ detection/OCR sang state dùng trực tiếp
- [ ] Action execution thật với map tọa độ production
- [ ] Post-action verification production
- [ ] Decision engine Tiến Lên hoàn chỉnh
- [ ] Single-bot playable end-to-end demo
- [ ] Multi-bot end-to-end gameplay supervision

## 5. Batch local hiện đang chờ push

- [x] `contracts/`
- [x] `docs/epics/`
- [x] `.github/ISSUE_TEMPLATE/agent_work_item.md`
- [x] `tests/test_contract_interfaces.py`
- [x] `agent_handoff_bundle/FULL_PROJECT_HANDOFF_VI.md`
- [x] `agent_handoff_bundle/index.html`
- [x] File checklist này: `agent_handoff_bundle/WORK_COMPLETION_CHECKLIST_VI.md`

## 6. Reality check về GitHub

- [x] Remote `origin/main` hiện đang ở commit `bd6b6c6`
- [ ] Các cập nhật local ở checklist này chưa nằm trên GitHub tại thời điểm file được tạo
- [x] Nếu cần agent khác nắm đúng bức tranh mới nhất ngay bây giờ, nên gửi bundle local chứ không chỉ gửi link remote

## 7. Thứ tự đọc đề xuất cho agent mới

1. `agent_handoff_bundle/WORK_COMPLETION_CHECKLIST_VI.md`
2. `agent_handoff_bundle/FULL_PROJECT_HANDOFF_VI.md`
3. `agent_handoff_bundle/index.html`
4. `docs/epics/README.md`
5. `contracts/interfaces.py`
6. `tests/test_contract_interfaces.py`

## 8. Ghi chú để tránh hiểu nhầm

- [x] Có contract, epic và test không đồng nghĩa gameplay bot đã xong.
- [x] Những mục perception, state, action, verify, decision vẫn là phần cần làm tiếp thật sự.
- [x] Checklist này cố tình phân biệt rõ `implemented`, `scaffold`, và `not finished` để không đánh dấu nhầm tiến độ.

## 9. Phạm vi pass này

- [x] Pass này chỉ thêm checklist và làm mới snapshot git status trong bundle
- [x] Không tự ý sửa logic runtime, contract, action, perception, hay config production
