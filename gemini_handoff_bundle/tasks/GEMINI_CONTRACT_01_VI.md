# GEMINI-CONTRACT-01

## Mục tiêu

Ổn định serialization và compatibility fixtures cho contracts dùng giữa process/replay. Không thay đổi card/state/action semantics hiện hữu và không tự khóa module.

## Setup bắt buộc

```powershell
git clone https://github.com/weijinn97-ai/tienlen-bot.git tienlen-bot-gemini
cd tienlen-bot-gemini
git checkout gemini-contract-01-baseline
git switch -c agent/gemini-contract-01
py -3 -m unittest discover -s tests -v
py -3 tools/check_module_governance.py
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
```

Baseline phải có `110/110` test pass. Nếu khác, dừng và ghi `GEMINI_CONTRACT_01_OUTPUT/BLOCKERS.md`; không sửa test cũ.

## Phạm vi được phép

Được tạo mới:

- `contracts/serialization.py`
- `tests/test_contract_serialization.py`
- `tests/fixtures/contracts_v1/**`
- `docs/acceptance/contracts/0.2.0/**`
- `GEMINI_CONTRACT_01_OUTPUT/**`

Chỉ được sửa file hiện hữu `contracts/__init__.py` để export public serialization API.

Cấm sửa `contracts/interfaces.py`, `.github/module-registry.json`, mọi file `bot/**`, test cũ, replay format và dependency files. Nếu thiết kế yêu cầu sửa các file này, dừng và báo blocker.

## API yêu cầu

Tạo API public, tên rõ ràng và type hinted, tối thiểu:

```python
CONTRACT_SCHEMA_VERSION = 1
contract_to_dict(value) -> dict
contract_from_dict(payload) -> supported contract
contract_to_json(value) -> str
contract_from_json(document) -> supported contract
```

Có thể chọn tên tương đương nếu nhất quán và export qua `contracts/__init__.py`.

Các type bắt buộc round-trip:

- `Rect`
- `DetectedCard`
- `CardCombo`
- `ButtonState`
- `TurnOwnerEvidence`
- `PerceptionSnapshot`
- `TableState`
- `VerifySpec`
- `ActionPlan`
- `ConsensusSpec`

## Format và validation

1. Envelope có `schema_version`, `contract_type`, `payload`.
2. JSON canonical: UTF-8, key order deterministic, không NaN/Infinity.
3. Enum serialize bằng `.value` hoặc tên đã document; một quy ước duy nhất.
4. Mapping có enum key phải chuyển sang key string ổn định và phục hồi đúng type.
5. Tuple phải phục hồi thành tuple khi contract yêu cầu.
6. Card chỉ dùng encoding contract `3S..2H`; không thêm encoding thứ hai.
7. Không dùng pickle, eval, dynamic import hoặc arbitrary class construction.
8. Unknown `schema_version`/`contract_type`, missing field, extra field, invalid enum/card/confidence/count phải fail với exception/reason rõ ràng.
9. Không silently drop field hoặc tự đoán default khi fixture gửi field sai/thiếu.
10. JSON từ cùng object phải byte-for-byte deterministic.

## Compatibility fixtures

Tạo fixture v1 cố định dưới `tests/fixtures/contracts_v1/` cho tối thiểu:

- full `PerceptionSnapshot` có cards, counts, turn evidence và buttons;
- full `TableState` có selected cards, last combo và phase;
- `ActionPlan` PLAY có `VerifySpec`;
- `ActionPlan` WAIT tối giản.

Fixture phải không chứa secret/room thật. Test phải đọc fixture từ disk, deserialize, serialize lại và so sánh canonical JSON đúng kỳ vọng. Fixture v1 không được tự rewrite trong test.

## Test bắt buộc

Tạo duy nhất `tests/test_contract_serialization.py` và bao phủ:

- round-trip từng type bắt buộc;
- canonical deterministic JSON;
- fixture compatibility;
- nested enum/mapping/tuple;
- malformed JSON;
- unknown schema/type;
- missing/extra fields;
- invalid card/count/confidence/enum;
- consumer smoke với `GameStateAdapter`, replay `table_state_to_dict/from_dict` hoặc action pipeline mà không sửa consumer.

Toàn bộ test cũ và test mới phải pass.

## Evidence

Tạo `docs/acceptance/contracts/0.2.0/` gồm:

- `README.md`
- `commands.txt`
- `metrics.json`
- `artifacts.sha256`
- `failures.md`

Đề xuất version `0.2.0 CANDIDATE`. Không sửa registry, không ghi `LOCKED`, không tạo tag `contracts-v1.0.0`; chỉ chủ repo được quyết định sau review.

## Kiểm tra cuối

```powershell
powershell -ExecutionPolicy Bypass -File gemini_handoff_bundle/guard_scope.ps1
py -3 -m unittest discover -s tests -p "test_contract_serialization.py" -v
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q bot contracts tools
py -3 tools/check_module_governance.py
git diff --check
git status --short
```

Chỉ stage từng file whitelist. Commit `Add stable contract serialization fixtures`, push branch `agent/gemini-contract-01`, mở draft PR `Relates to #2`; không tự merge/close issue.

Lưu final report tại `GEMINI_CONTRACT_01_OUTPUT/FINAL_REPORT.md` theo template. Nếu guard fail hoặc cần ra ngoài scope, dừng và ghi blocker.
