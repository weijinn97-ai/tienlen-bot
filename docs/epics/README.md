# Epic Roadmap

Các epic dưới đây là bộ work breakdown chuẩn hóa theo quyết định mới nhất, trong đó **Phase 2 được tách thành `2A` và `2B`**. Tổng cộng có **5 epic**:

1. [EPIC_01_CONTRACTS_AND_BASELINES.md](/D:/tienlenOPus/tienlen-bot/docs/epics/EPIC_01_CONTRACTS_AND_BASELINES.md:1)
2. [EPIC_02A_DATA_BOOTSTRAP_AUTOMATION.md](/D:/tienlenOPus/tienlen-bot/docs/epics/EPIC_02A_DATA_BOOTSTRAP_AUTOMATION.md:1)
3. [EPIC_02B_TURN_OWNER_AND_UI_SIGNALS.md](/D:/tienlenOPus/tienlen-bot/docs/epics/EPIC_02B_TURN_OWNER_AND_UI_SIGNALS.md:1)
4. [EPIC_03_TABLE_STATE_AND_CONSENSUS.md](/D:/tienlenOPus/tienlen-bot/docs/epics/EPIC_03_TABLE_STATE_AND_CONSENSUS.md:1)
5. [EPIC_04_ACTION_VERIFY_AND_CONTROL.md](/D:/tienlenOPus/tienlen-bot/docs/epics/EPIC_04_ACTION_VERIFY_AND_CONTROL.md:1)

Lưu ý:

- `EPIC_01` là foundation contract và naming alignment.
- `EPIC_02A` tập trung vào dữ liệu và automation thu ảnh.
- `EPIC_02B` tách riêng turn owner / UI signals để không phụ thuộc full card perception.
- `EPIC_03` mới đi sâu vào `TableState`, `last_played_combo`, `buttons`, `game_phase`, consensus.
- `EPIC_04` gom `action + verify + single-bot playable loop`, theo chốt A primary, B escalation, rồi mới nối supervisor/resource hardening.
