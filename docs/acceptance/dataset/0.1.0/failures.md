# Open Dataset Gates

- All 36 committed source images are missing reviewed production bounding boxes.
- pHash threshold 6 connects 32 images across submissions; capture boundaries then form one 36-image component. A leakage-safe val/test split is impossible with the current set.
- `match_id` is unavailable for all 36 images. Submission boundaries are used conservatively instead of guessing.
- Current sources cover `MY_HAND` only; there is no reviewed `TABLE_PLAY` ground truth.
- There are no locked `BUTTON_UI`/OCR annotations and the required negative/disabled button deficit is 2,000 frames.
- Second review has been selected in `annotation_review.csv`, but no human review result has been recorded.

Required next input: independently captured sessions/matches/rounds with explicit metadata and reviewed bbox annotations, including table plays and button/OCR hard negatives. Do not train until inventory produces non-empty leakage-safe train/val/test splits.
