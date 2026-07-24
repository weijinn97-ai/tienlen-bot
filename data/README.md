# Data Directory

This directory contains dataset intake metadata and a small legacy/bootstrap
sample. It is not the production training store. Production raw images,
labels, runs, and model weights must remain on the approved external storage
workspace and be referenced from Git by manifests and SHA-256 checksums.

## Structure

The `images/` and `labels/` layout below describes the external training
workspace. The repository may retain historical/bootstrap samples, but new
production binaries must not be added here.

*   `images/`: Contains all the raw image files (e.g., screenshots from MEmu Player).
    *   `train/`: Images specifically for training.
    *   `val/`: Images specifically for validation.
    *   `test/`: Images specifically for testing.
*   `labels/`: Contains the corresponding YOLO format label files (`.txt`) for each image in the `images/` directory.
    *   `train/`: Labels for training images.
    *   `val/`: Labels for validation images.
    *   `test/`: Labels for testing images.
*   `submissions/`: Historical intake metadata for user-provided screenshots before full labeling.
    *   `<batch_name>/raw/`: Existing historical inputs and pointers; new production raw files belong in external storage.
    *   `<batch_name>/manifest.csv`: Shared metadata for each screenshot.
    *   `<batch_name>/README.md`: Short summary of the batch.

Each image file in `images/` must have a corresponding label file in `labels/` with the same base name (e.g., `image1.png` in `images/train/` will have `image1.txt` in `labels/train/`).

## Recommended Workflow for User Screenshots

When screenshots come from a user chat or manual capture, do not move them straight into `images/train/` yet.

1.  Import them into a shared batch:
    ```bash
    py -3 tools/import_user_screenshots.py --batch-name your_batch_name --files "C:\path\shot1.png" "C:\path\shot2.png"
    ```
2.  Update the batch `manifest.csv` with visible cards, room ID, and review notes.
3.  Export the combined Google Sheet index:
    ```bash
    py -3 tools/export_image_index_csv.py
    ```
4.  Only after review and labeling should selected files move into `images/train|val|test` and `labels/train|val|test`.

This keeps raw intake, card splitting, and final training labels separated so multiple agents can work safely in parallel.

## Contribution Guidelines for Data

To contribute new training data (images and labels), please follow these steps to ensure consistency and quality:

1.  **Capture Screenshots:**
    *   Capture screenshots from the MEmu Player game using `adb_capture.py` or `scrcpy_capture.py` (from the `bot/capture` module).
    *   Ensure a variety of scenarios are covered: different numbers of players (2, 3, 4), various card combinations, different levels of card overlapping, and cards being selected (highlighted/raised).
    *   Save raw screenshots to a temporary local directory.

2.  **Labeling:**
    *   Use a suitable labeling tool (e.g., [LabelImg](https://github.com/tzutalin/labelImg), [Roboflow Annotate](https://docs.roboflow.com/annotate)) to annotate the cards in the captured images.
    *   **Important:** Each card (52 classes) must be accurately identified, and its bounding box precisely drawn. Pay close attention to partially visible or overlapping cards; label only the visible portion if the card is partially obscured, but ensure the class is correct.
    *   For selected cards, label them as their base class (e.g., 'A_spades') and the detection logic in `card_recognizer.py` will handle the 'selected' state based on Y-coordinate analysis.
    *   The output format for labels **must be YOLO (`.txt`)**.

3.  **Organize the external training workspace:**
    *   After labeling, place images and labels in the approved external
        training workspace, not in this repository's `data/` directory.
    *   Keep separate `train`, `val`, and `test` directories and enforce the
        group-first split rules in `docs/TRAINING_PLAN_FINAL.md`.
    *   Keep the original raw files immutable and record their paths and
        checksums in the inventory.

4.  **Create the local dataset configuration:**
    *   Create `dataset.yaml` on the VPS with a resolved absolute path to the
        external workspace and the fixed 52-card class names.
    *   Do not commit a machine-specific dataset YAML to this repository.

5.  **Publish metadata only:**
    *   Do not add new raw images, labels, runs, or weights to Git, including
        through Git LFS. Store them on the approved VPS/NAS/S3 workspace.
    *   Commit only the reviewed inventory, split manifest, annotation review,
        metrics, model-card metadata, and SHA-256/checksum files.
    *   Never place a machine-specific absolute path in a committed
        `dataset.yaml`.

6.  **Create a Pull Request (PR):**
    *   Open a Pull Request from your branch to the `main` branch of the original `tienlen-bot` repository.
    *   Provide a detailed description of the data you've added, including the scenarios covered and any specific challenges encountered during labeling.

## Data Versioning and Reproducibility

For reproducibility, every external dataset release must have a stable
dataset version and SHA-256 manifest. DVC or another external artifact store
may be introduced later, but no new binary dataset or model is committed to
this repository by default.
