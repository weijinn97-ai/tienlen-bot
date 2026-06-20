# Data Directory

This directory contains all the images and labels used for training the YOLOv8 model for card recognition. The goal is to maintain a centralized, version-controlled dataset that can be easily updated and utilized by all contributors and agents.

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

3.  **Organize and Prepare Files for Upload:**
    *   After labeling, move the new image files into the appropriate `images/train/`, `images/val/`, or `images/test/` subdirectories within your local `tienlen-bot/data` folder.
    *   Place their corresponding label files (`.txt`) into the respective `labels/train/`, `labels/val/`, or `labels/test/` subdirectories.
    *   Maintain a clear separation between training, validation, and testing sets to avoid data leakage.

4.  **Update `dataset.yaml` (if necessary):**
    *   The `configs/dataset.yaml` file defines the dataset path and class names. If you introduce new classes (unlikely for a standard 52-card deck but possible for special game elements), ensure this file is updated accordingly.

5.  **Commit and Push (using Git LFS for large files):**
    *   For image and label files, especially if they are large in number or size, **we will use Git Large File Storage (LFS)**. This prevents bloating the Git repository history with binary files.
    *   **First-time setup for Git LFS:**
        ```bash
        git lfs install
        git lfs track "data/images/*.png"
        git lfs track "data/images/*.jpg"
        git lfs track "data/labels/*.txt"
        git add .gitattributes
        ```
    *   Add your new image and label files to Git:
        ```bash
        git add data/images/train/your_image.png data/labels/train/your_image.txt
        # ... add all new files
        ```
    *   Commit your changes with a descriptive message:
        ```bash
        git commit -m "feat(data): Add new training images and labels for [specific scenario]"
        ```
    *   Push your changes to your forked repository:
        ```bash
        git push origin your-feature-branch
        ```

6.  **Create a Pull Request (PR):**
    *   Open a Pull Request from your branch to the `main` branch of the original `tienlen-bot` repository.
    *   Provide a detailed description of the data you've added, including the scenarios covered and any specific challenges encountered during labeling.

## Data Versioning and Reproducibility

To ensure data versioning and reproducibility, especially as the dataset grows, we will integrate [DVC (Data Version Control)](https://dvc.org/) in a future phase. DVC allows us to track large files and directories in Git without committing their contents directly, making it easier to manage dataset updates and switch between different versions of the data. For now, Git LFS will handle the storage of large image files efficiently.
