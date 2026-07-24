# Perception Training Plan - Locked Requirements

Status: `BLOCKED_ON_DATA`

This document is the operational source of truth for production perception
dataset preparation and training. It does not authorize training until every
pre-training gate below is evidenced. Raw images and model weights must stay
outside Git.

## 1. Dataset Allocation

The required dataset is split into independent purposes:

| Set | Minimum | Purpose | May train card detector? |
|---|---:|---|---|
| New production images | 3,000 | Hand, table, UI and OCR coverage | Yes, after annotation QA |
| New production images | 5,000 target | Preferred coverage and diversity | Yes, after annotation QA |
| Legacy images | 36 | Existing `MY_HAND` images | Yes, train only |
| Locked UI negatives | 2,000 | UI safety evaluation only | No |

The 2,000 UI-negative frames are a separate locked test set. They must not be
counted as card-detector training images and must not be mixed into the card
validation set.

The 3,000-5,000 new production images must contain both `MY_HAND` and
`TABLE_PLAY`, plus real UI states and OCR fields where present. The dataset
must include hand sizes from 13 down to 1, selected and unselected cards,
single-card and multi-card table plays, animation/occlusion cases, and the
actual MEmu layout variations.

## 2. Canonical Metadata and Status Values

`inventory.csv` must preserve the repository schema:

```text
asset_id,relative_path,submission,session_id,match_id,round_id,zone,
sha256,phash64,width,height,annotation_path,annotation_status,error
```

Allowed `annotation_status` values are exactly:

```text
PRESENT, MISSING, INVALID, NOT_REQUIRED
```

Do not use `APPROVED`, `approved`, `pending`, `rejected`, or other aliases in
the inventory. If an external labeling tool uses `approved`, map it to
`PRESENT` at import time and record the original value in the QA notes.

`NOT_REQUIRED` is only valid for explicitly non-card assets such as UI safety
negative frames. It must never hide a missing card annotation.

Missing metadata must be recorded as `UNKNOWN`; agents must never invent
session, match, or round values.

## 3. Legacy 36-Image Rule

The existing 36 images are legacy `MY_HAND` data with incomplete provenance.

- Annotate all 36 using the production card bounding-box rules.
- Assign one stable group, for example `legacy_36_unknown`.
- Keep the entire group in `train`; do not random-split it into validation or
  test.
- Preserve unknown provenance as `UNKNOWN`; never fabricate IDs.
- Include the 36 images in inventory and checksum reports.
- Do not claim that these images provide session diversity.

## 4. Split Manifest and Leakage Gates

`split_manifest.csv` must contain at least:

```text
asset_id,relative_path,group_id,split,split_reason
```

Additional metadata columns are allowed, but these names and meanings are
mandatory. Allowed split values are `train`, `val`, and `test`.

Rules:

- Split by group first, never by individual frame.
- A session, match, round, burst, exact duplicate, or near-duplicate group
  must occur in only one split.
- Card data must have real train, validation, and locked card-test records.
  “Test if available” is not acceptable.
- Every class present in the production scope must be represented in train,
  validation, and card test, unless the manifest explicitly records a reviewed
  exception and blocks training.
- The locked UI-negative test must contain at least 5 sessions and 50
  independent sequences.
- The 36 legacy images remain train-only.

Recommended starting allocation for the new production images is 70% train,
15% validation, and 15% card test. Zero leakage takes priority over exact
percentages.

## 5. Annotation Rules

Use separate datasets/models for:

- `hand_cards`: 52 card classes.
- `table_cards`: 52 card classes.
- `buttons_ui`: UI state detection or fixed-ROI classifier.
- `ocr_fields`: OCR for text/number fields only.

Do not mix UI button classes into a card detector. Do not use OCR to replace
card classification.

Card class IDs are fixed and must match the contract exactly:

```text
0:3S 1:3C 2:3D 3:3H ... 48:2S 49:2C 50:2D 51:2H
```

Use `S=Spades`, `C=Clubs`, `D=Diamonds`, `H=Hearts`. Annotate each visible
card separately. Do not guess hidden card boundaries or labels. If rank or
suit cannot be reviewed confidently, mark the object ignored and record the
reason instead of forcing a label.

For UI-negative frames, record an explicit state such as
`play_disabled`, `pass_disabled`, `popup`, `animation`, or `outside_table`,
and require `play_enabled=false`. These are safety labels, not card labels.

## 6. Mandatory QA Before Training

- Review 100% of validation and test annotations with a second reviewer.
- Review at least 20% of training annotations with a second reviewer.
- Reject invalid class IDs, empty/invalid boxes, out-of-image boxes, missing
  image-label pairs, and duplicate/leaked groups.
- Review confusion pairs `S/C`, `D/H`, `6/9`, `10/J`, and red-card color
  changes.
- Verify the 2,000 UI-negative frames contain zero `play_enabled` ground-truth
  records.
- Produce `annotation_review.csv`, inventory, split manifest, coverage report,
  and SHA-256 checksums.

Training is forbidden if any pre-training gate fails. The report must state
`training_authorized=false` when blocked.

## 7. VPS Training Rules

Raw data, `best.pt`, runs, and large plots belong on the VPS/NAS/S3, not in
Git. Commit only manifests, reports, checksums, and reproducible instructions.

Create `dataset.yaml` locally on the VPS with a resolved absolute path. Do
not commit a machine-specific path or assume that Ultralytics expands
`$DATA_ROOT` inside YAML.

Before training, record Python, PyTorch, CUDA, GPU, Ultralytics, and `pip
freeze` in `environment.txt`. Stop if `torch.cuda.is_available()` is false;
do not silently train on CPU.

Train `hand_cards` and `table_cards` independently. Start with one deterministic
baseline seed, then use seeds 41 and 73 only after the baseline is valid. Do
not increase epochs indefinitely to compensate for bad labels or missing
coverage.

## 8. Acceptance Gates

Report per-class precision, recall, F1, worst classes, confusion matrix,
false positives, exact hand-set accuracy, exact table-combo accuracy, and
selected/occluded/animation subsets. Also report warm-up, p50, p95, p99,
throughput, and peak VRAM.

Candidate thresholds:

- Hand: precision/recall >= 0.99, exact hand set >= 98%, minimum class recall
  >= 95%.
- Table: precision/recall >= 0.98, exact combo >= 97%, minimum class recall
  >= 92%.
- Button state exact accuracy >= 99.5%.
- Critical OCR exact accuracy >= 99%; low confidence must return `UNKNOWN`.
- No false `PLAY enabled` on the locked 2,000-frame UI-negative test.
- Card-model p95 <= 70 ms each on target GPU; full perception target <= 125 ms.
- No leakage by SHA-256, pHash, session, match, round, or burst.

mAP alone is not an acceptance decision. A single wrong card can create a
wrong action, so exact-state metrics and fail-safe behavior are mandatory.

## 9. Runtime Qualification After Offline Acceptance

Offline model acceptance does not authorize unattended gameplay. The remaining
gates are:

- Locked replay: regular transitions use 2/3 consensus and critical
  transitions use 3/4 consensus; the newest frame must be in the consensus.
- Read-only live soak: at least 2 hours or 20 games, with no taps.
- At least 100 supervised valid actions, each with selection verification,
  enabled-button recapture, and post-action verification.
- Required result: zero wrong-card taps, zero false `PLAY`, and zero out-of-turn
  actions. Timeout or conflict must fail safe to `WAIT`/stop.

Do not enable unattended or real-money gameplay based only on training metrics.

## 10. Required Deliverables

Each training run must provide:

```text
model_card.md
best.pt.sha256
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

`model_card.md` must include source commit, dataset version/hash, date,
complete command, seed, actual epochs/early-stop reason, validation/test
metrics, worst classes, exact-state metrics, latency, and known limitations.

## 11. Pre-Training Checklist

- [ ] At least 3,000 new production images collected.
- [ ] `MY_HAND` and `TABLE_PLAY` coverage is present.
- [ ] All 36 legacy images annotated and kept in `legacy_36_unknown` train group.
- [ ] Exactly 2,000 distinct UI-negative test frames reserved.
- [ ] UI negatives cover at least 5 sessions and 50 sequences.
- [ ] Canonical inventory statuses are used.
- [ ] Real train/val/card-test splits exist; no “if available” test split.
- [ ] No leakage by hash, pHash, group, session, match, round, or burst.
- [ ] 100% val/test and 20% train annotation review completed.
- [ ] All 52 classes are covered or an explicit blocking exception exists.
- [ ] GPU environment and checksums are recorded.
- [ ] `training_authorized=true` is produced by QA tooling.

Until every box is checked, the production perception module remains
`IN_PROGRESS` and the dataset gate remains `BLOCKED_ON_DATA`.
