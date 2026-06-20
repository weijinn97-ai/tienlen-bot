# 🃏 Tiến Lên Bot

This project aims to develop a real-time Tiến Lên (Vietnamese card game) bot that operates on the MEmu Android emulator. The bot will leverage YOLOv8 for accurate card recognition, advanced computer vision techniques for game state tracking, and robust stability mechanisms to prevent game crashes.

## Features

*   **Real-time Card Recognition:** Utilizes YOLOv8 to accurately identify cards in hand (even when overlapping) and cards played by opponents.
*   **Dynamic Game State Tracking:** Monitors the game state, including player turns, remaining cards, and active combos.
*   **Robust Stability:** Implements crash handling and connection monitoring to ensure continuous operation.
*   **Detailed Logging:** Records game events and screenshots for debugging and analysis.
*   **AI Agent (Future):** Integrates a decision-making AI to play the game strategically.

## Project Structure

```
tienlen-bot/
├── bot/                  # Core bot logic and modules
│   ├── capture/          # Screen capture and processing
│   ├── recognition/      # Card recognition (YOLOv8, OCR)
│   ├── stability/        # Crash handling, connection monitoring
│   ├── state/            # Game state management, card tracking
│   ├── actions/          # ADB tap/swipe actions
│   └── logging/          # Game event logging
├── data/                 # Training data (images, labels)
│   ├── images/           # Raw image files (train, val, test)
│   └── labels/           # YOLO format label files (train, val, test)
├── configs/              # Configuration files (YOLO dataset, ROIs)
├── models/               # Trained YOLOv8 models
├── tests/                # Unit and integration tests
├── .gitignore
├── README.md
└── CONTRIBUTING.md
```

## Setup and Installation

*(To be filled in later with detailed instructions)*

## Contribution

We welcome contributions to this project! Please refer to `CONTRIBUTING.md` for guidelines on how to contribute.

## License

*(To be filled in later)*
