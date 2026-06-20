# Data Directory

This directory contains all the images and labels used for training the YOLOv8 model for card recognition.

## Structure

*   `images/`: Contains all the raw image files (e.g., screenshots from MEmu Player).
    *   `train/`: Images specifically for training.
    *   `val/`: Images specifically for validation.
    *   `test/`: Images specifically for testing.
*   `labels/`: Contains the corresponding YOLO format label files (`.txt`) for each image in the `images/` directory.
    *   `train/`: Labels for training images.
    *   `val/`: Labels for validation images.
    *   `test/`: Labels for testing images.

Each image file in `images/` must have a corresponding label file in `labels/` with the same base name (e.g., `image1.png` in `images/train/` will have `image1.txt` in `labels/train/`).

## Contribution Guidelines for Data

To contribute new training data (images and labels), please follow these steps:

1.  **Capture Screenshots:** Capture screenshots from the MEmu Player game, ensuring a variety of scenarios (different numbers of players, various card combinations, overlapping cards, selected cards).
2.  **Labeling:** Use a labeling tool (e.g., [Roboflow Annotate](https://docs.roboflow.com/annotate), [LabelImg](https://github.com/tzutalin/labelImg)) to annotate the cards in the captured images. Ensure that each card is correctly identified and its bounding box is accurately drawn. The output format should be YOLO (`.txt`).
3.  **Organize Files:** Place the new image files into the appropriate `images/train/`, `images/val/`, or `images/test/` subdirectories. Place their corresponding label files into the respective `labels/train/`, `labels/val/`, or `labels/test/` subdirectories.
4.  **Update `dataset.yaml`:** If you are adding new classes or making significant changes, ensure the `configs/dataset.yaml` file is updated accordingly.
5.  **Commit and Push:** Commit your changes to a new branch and create a Pull Request for review. For large datasets, consider using Git LFS (Large File Storage) to manage image files.

## Data Versioning

For better data management and reproducibility, we recommend using [DVC (Data Version Control)](https://dvc.org/) in the future to version control the datasets, especially as the dataset grows large. For now, direct commits of images (if not too large) are acceptable.
