# Limitations

- No production YOLO weights are loaded by this task.
- No production OCR dataset or locked UI-negative replay is evaluated here.
- No live MEmu action or ADB input is performed.
- Detector accuracy, latency, and model qualification remain outstanding.
- The pipeline is a candidate integration boundary and must not be treated as
  production-ready until the dataset, model, replay, and supervised-action
  gates pass.
