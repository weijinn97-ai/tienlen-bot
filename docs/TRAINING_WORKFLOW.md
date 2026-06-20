# Training and Model Comparison Workflow

This document outlines the workflow for training YOLOv8 models and comparing their performance within the Tiến Lên Bot project. The goal is to enable collaborative development and continuous improvement of the card recognition model.

## 1. Standardized Training Script

All agents will use a standardized training script, `bot/models/train_yolo.py`, which will encapsulate the training process. This script will:

*   Load the dataset defined in `configs/dataset.yaml`.
*   Initialize a YOLOv8 model (e.g., `yolov8n.pt` for nano, `yolov8s.pt` for small).
*   Train the model for a specified number of epochs.
*   Save the trained model weights and training logs.

**Example usage of `train_yolo.py`:**

```bash
python bot/models/train_yolo.py --epochs 50 --batch-size 16 --imgsz 640 --name my_experiment_v1
```

## 2. Evaluation Metrics and Logging

After training, the model's performance will be evaluated using standard object detection metrics. The `train_yolo.py` script will automatically perform validation and log key metrics.

*   **Metrics:** Mean Average Precision (mAP) at different Intersection over Union (IoU) thresholds (e.g., `mAP50`, `mAP50-95`), Precision, Recall.
*   **Logging:** Training and validation results (metrics, loss curves) will be logged using [Weights & Biases (W&B)](https://wandb.ai/) or [MLflow](https://mlflow.org/). This allows for easy visualization and comparison of different training runs.

Each training run will generate a unique experiment ID, and its results will be stored in a centralized logging platform. This enables agents to compare their model's performance against previous runs.

## 3. Model Storage and Versioning

Trained model weights (`.pt` files) will be stored in the `models/` directory. To manage different versions and experiments, a clear naming convention should be followed (e.g., `yolov8n_my_experiment_v1.pt`).

For larger models or more complex versioning needs, [DVC (Data Version Control)](https://dvc.org/) can be extended to manage model artifacts, similar to how it will be used for datasets.

## 4. Agent Workflow for Training and Comparison

1.  **Pull Latest Changes:** Before starting any training, agents should pull the latest changes from the `main` branch to ensure they have the most up-to-date code and dataset.
    ```bash
    git pull origin main
    ```
2.  **Prepare Data:** Ensure the `data/` directory contains the desired images and labels. If new data is added, follow the `data/README.md` guidelines.
3.  **Run Training:** Execute the `train_yolo.py` script with appropriate parameters. Make sure to provide a unique `--name` for your experiment.
    ```bash
    python bot/models/train_yolo.py --epochs 50 --batch-size 16 --imgsz 640 --name agent_X_run_Y
    ```
4.  **Review Results:** Access the W&B/MLflow dashboard to review the training logs and compare the performance of your model with previous runs. Pay attention to `mAP50`, `mAP50-95`, and loss curves.
5.  **Evaluate on Test Set:** If the model shows promising results, evaluate it on the `test` dataset to get an unbiased performance estimate.
    ```bash
    python bot/models/train_yolo.py val --data configs/dataset.yaml --model models/yolov8n_agent_X_run_Y.pt
    ```
6.  **Propose Model Update (Pull Request):** If your trained model significantly outperforms existing models or addresses a specific issue, create a Pull Request:
    *   Add the new model weights to `models/`.
    *   Update `README.md` or a dedicated `MODELS.md` (if created) to document the new model, its performance, and the conditions under which it was trained.
    *   Provide a summary of the W&B/MLflow run in the PR description.

## 5. Continuous Integration (CI) for Model Evaluation (Future)

In a more advanced setup, CI/CD pipelines can be implemented to automatically:

*   Trigger model training on new data contributions.
*   Evaluate newly trained models against a benchmark.
*   Generate reports and notify contributors of performance changes.

This automated process will streamline model development and ensure that only high-performing models are integrated into the main project.
