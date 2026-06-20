# Contributing to Tiến Lên Bot

We welcome contributions to the Tiến Lên Bot project! By contributing, you help us build a more robust and intelligent bot.

## How to Contribute

1.  **Fork the Repository:** Start by forking the `tienlen-bot` repository to your GitHub account.
2.  **Clone Your Fork:** Clone your forked repository to your local machine:
    ```bash
    git clone https://github.com/YOUR_USERNAME/tienlen-bot.git
    cd tienlen-bot
    ```
3.  **Create a New Branch:** Create a new branch for your feature or bug fix:
    ```bash
    git checkout -b feature/your-feature-name
    ```
4.  **Make Your Changes:** Implement your changes, whether it's code, documentation, or data.
5.  **Commit Your Changes:** Write clear and concise commit messages.
    ```bash
    git commit -m "feat: Add new card recognition logic"
    ```
6.  **Push to Your Fork:** Push your changes to your forked repository:
    ```bash
    git push origin feature/your-feature-name
    ```
7.  **Create a Pull Request (PR):** Open a Pull Request from your branch to the `main` branch of the original `tienlen-bot` repository. Provide a detailed description of your changes.

## Contribution Guidelines

### Code Contributions

*   **Code Style:** Follow PEP 8 for Python code. Use a linter (e.g., `flake8`, `black`) to ensure consistency.
*   **Documentation:** Document your code clearly, especially for new functions, classes, and complex logic.
*   **Testing:** Write unit tests for new features and ensure existing tests pass.
*   **Modularity:** Keep your code modular and focused on single responsibilities.

### Data Contributions (Images and Labels)

This is crucial for improving the card recognition model. Please refer to `data/README.md` for detailed instructions on how to contribute images and labels.

**Key principles for data contribution:**

*   **Diversity:** Contribute images from various game states, lighting conditions, and numbers of players.
*   **Accuracy:** Ensure labels are highly accurate. Incorrect labels can degrade model performance.
*   **Completeness:** Label all visible cards in an image.
*   **Overlap Handling:** Pay special attention to labeling overlapping cards, ensuring bounding boxes accurately capture the visible parts.
*   **Selected Cards:** If contributing images with selected cards, ensure they are labeled correctly.

### Review Process

All Pull Requests will be reviewed by maintainers. Please be responsive to feedback and be prepared to make adjustments.

## Questions?

If you have any questions or need assistance, please open an issue on the GitHub repository.
