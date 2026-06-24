from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_DIR = ROOT / "docs" / "google_sheet_seed"
DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1pQ8eU043r1phOG67BsO9gDmUK2TKjVAZPSz6MccJ_vc/edit?gid=0"
)
DEFAULT_VIEWPORT = {"width": 1600, "height": 1200}
GRID_FOCUS_OFFSET_X = 60
GRID_FOCUS_OFFSET_Y = 35


@dataclass(frozen=True)
class SeedSheet:
    tab_name: str
    rows: list[list[str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a publicly editable Google Sheet from local CSV templates."
    )
    parser.add_argument(
        "--sheet-url",
        default=DEFAULT_SHEET_URL,
        help="Google Sheet edit URL that allows public or account-based editing.",
    )
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=DEFAULT_SEED_DIR,
        help="Directory that contains CSV seed files.",
    )
    parser.add_argument(
        "--chrome-path",
        type=Path,
        default=None,
        help="Optional explicit path to chrome.exe or msedge.exe.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show the browser window while seeding.",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=8000,
        help="Initial wait after page load in milliseconds.",
    )
    parser.add_argument(
        "--navigation-timeout-ms",
        type=int,
        default=180000,
        help="Navigation timeout in milliseconds for loading the Google Sheet.",
    )
    return parser.parse_args()


def load_seed_sheets(seed_dir: Path) -> list[SeedSheet]:
    csv_paths = sorted(seed_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No CSV seed files found in: {seed_dir}")

    sheets: list[SeedSheet] = []
    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        if not rows:
            continue
        sheets.append(SeedSheet(tab_name=csv_path.stem, rows=rows))

    if not sheets:
        raise ValueError(f"Seed directory has CSV files but all are empty: {seed_dir}")

    return sheets


def rows_to_tsv(rows: Iterable[Iterable[str]]) -> str:
    return "\n".join("\t".join(cell for cell in row) for row in rows)


def detect_browser_path(explicit_path: Path | None) -> str:
    if explicit_path:
        if explicit_path.exists():
            return str(explicit_path)
        raise FileNotFoundError(f"Browser executable does not exist: {explicit_path}")

    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "Could not find Chrome or Edge. Pass --chrome-path with a browser executable."
    )


def import_playwright():
    try:
        from playwright.sync_api import Page, sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised manually
        raise RuntimeError(
            "Playwright is required. Install it with: py -3 -m pip install playwright"
        ) from exc

    return Page, sync_playwright


def list_sheet_tabs(page) -> list[str]:
    tabs = page.locator("div.docs-sheet-tab")
    names: list[str] = []
    for index in range(tabs.count()):
        name = tabs.nth(index).inner_text().strip()
        if name:
            names.append(name)
    return names


def open_tab(page, tab_name: str) -> None:
    page.locator("div.docs-sheet-tab", has_text=tab_name).first.click()
    page.wait_for_timeout(700)


def rename_active_tab(page, new_name: str) -> None:
    active_tab = page.locator("div.docs-sheet-active-tab").first
    active_tab.dblclick()
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.keyboard.type(new_name)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1000)


def create_and_rename_tab(page, tab_name: str) -> None:
    add_button = page.locator(
        'div.docs-sheet-add-button, div[aria-label="Thêm trang tính"], div[aria-label="Add sheet"]'
    ).first
    add_button.click()
    page.wait_for_timeout(1000)
    rename_active_tab(page, tab_name)


def ensure_initial_tab_name(page, target_tab_name: str) -> None:
    tab_names = list_sheet_tabs(page)
    if len(tab_names) != 1:
        return

    first_name = tab_names[0]
    if first_name in {"Sheet1", "Trang tính1", "Tong Quan"} and first_name != target_tab_name:
        rename_active_tab(page, target_tab_name)


def focus_grid(page) -> None:
    canvas = page.locator("canvas").first
    box = canvas.bounding_box()
    if box is None:
        raise RuntimeError("Could not locate the sheet canvas.")
    page.mouse.click(box["x"] + GRID_FOCUS_OFFSET_X, box["y"] + GRID_FOCUS_OFFSET_Y)
    page.wait_for_timeout(300)


def clear_active_sheet(page) -> None:
    page.locator("#t-name-box").click()
    page.keyboard.press("Control+A")
    page.keyboard.type("A1")
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    focus_grid(page)
    page.keyboard.press("Control+A")
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.wait_for_timeout(1200)


def paste_rows(page, rows: list[list[str]]) -> None:
    focus_grid(page)
    page.evaluate("text => navigator.clipboard.writeText(text)", rows_to_tsv(rows))
    page.keyboard.press("Control+V")
    page.wait_for_timeout(2500)


def seed_sheet(
    sheet_url: str,
    seed_sheets: list[SeedSheet],
    browser_path: str,
    headful: bool,
    wait_ms: int,
    navigation_timeout_ms: int,
) -> None:
    Page, sync_playwright = import_playwright()
    _ = Page

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not headful,
            executable_path=browser_path,
        )
        context = browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        page.set_default_navigation_timeout(navigation_timeout_ms)
        page.goto(
            sheet_url,
            wait_until="domcontentloaded",
            timeout=navigation_timeout_ms,
        )
        page.wait_for_timeout(wait_ms)
        page.locator("#t-name-box").wait_for(timeout=120000)
        page.locator("div.docs-sheet-tab").first.wait_for(timeout=120000)

        ensure_initial_tab_name(page, seed_sheets[0].tab_name)

        for index, seed_sheet_item in enumerate(seed_sheets):
            current_tabs = list_sheet_tabs(page)
            if seed_sheet_item.tab_name in current_tabs:
                open_tab(page, seed_sheet_item.tab_name)
            elif index == 0 and len(current_tabs) == 1:
                rename_active_tab(page, seed_sheet_item.tab_name)
            else:
                create_and_rename_tab(page, seed_sheet_item.tab_name)

            clear_active_sheet(page)
            paste_rows(page, seed_sheet_item.rows)
            print(f"Seeded tab: {seed_sheet_item.tab_name}")

        browser.close()


def main() -> int:
    args = parse_args()
    seed_sheets = load_seed_sheets(args.seed_dir)
    browser_path = detect_browser_path(args.chrome_path)

    seed_sheet(
        sheet_url=args.sheet_url,
        seed_sheets=seed_sheets,
        browser_path=browser_path,
        headful=args.headful,
        wait_ms=args.wait_ms,
        navigation_timeout_ms=args.navigation_timeout_ms,
    )
    print(f"Completed seeding {len(seed_sheets)} tab(s) into: {args.sheet_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
