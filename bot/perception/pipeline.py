"""Safe wiring layer for frame-to-typed-perception conversion.

The pipeline deliberately depends on small injected adapters. This keeps
runtime wiring testable without requiring production weights, OCR binaries, or
live emulator input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping, Protocol, Sequence

import numpy as np

from bot.perception.ocr import OcrText
from bot.perception.turn_owner import TurnOwnerDetection
from contracts.interfaces import (
    ButtonId,
    ButtonState,
    DetectedCard,
    GamePhase,
    PerceptionSnapshot,
    Rect,
    SeatPosition,
    TurnOwnerEvidence,
)
from bot.runtime.schemas import FrameEnvelope


class CardDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Sequence[DetectedCard]:
        ...


class ButtonDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Sequence[ButtonState]:
        ...


class OcrDetector(Protocol):
    def recognize(self, frame: np.ndarray) -> Mapping[str, OcrText]:
        ...


class TurnDetector(Protocol):
    def detect(
        self,
        frame: np.ndarray,
        *,
        previous_card_counts: Mapping[SeatPosition, int],
        current_card_counts: Mapping[SeatPosition, int],
    ) -> TurnOwnerDetection:
        ...


class FailureComponent(str, Enum):
    FRAME = "frame"
    CARDS = "cards"
    BUTTONS = "buttons"
    OCR = "ocr"
    TURN = "turn"


@dataclass(frozen=True)
class PipelineFailure:
    component: FailureComponent
    reason: str


@dataclass(frozen=True)
class PipelineResult:
    snapshot: PerceptionSnapshot | None
    ocr_fields: tuple[tuple[str, OcrText], ...]
    failures: tuple[PipelineFailure, ...]

    @property
    def ok(self) -> bool:
        return self.snapshot is not None and not self.failures


@dataclass(frozen=True)
class PerceptionAdapters:
    cards: CardDetector
    buttons: ButtonDetector
    ocr: OcrDetector | None = None
    turn: TurnDetector | None = None


def _safe_buttons() -> tuple[ButtonState, ...]:
    """Return conservative action states after a button detector failure."""

    safe_roi = Rect(0, 0, 1, 1)
    return tuple(
        ButtonState(
            button_id=button_id,
            label=button_id.value,
            roi=safe_roi,
            is_visible=False,
            is_enabled=False,
            confidence=0.0,
        )
        for button_id in (ButtonId.PLAY, ButtonId.PASS)
    )


def _validate_frame(frame: FrameEnvelope) -> np.ndarray:
    if not isinstance(frame, FrameEnvelope):
        raise TypeError("frame must be a FrameEnvelope.")
    if not frame.bot_id.strip() or not frame.frame_id.strip():
        raise ValueError("frame identity must be non-empty.")
    if frame.timestamp_ns <= 0 or frame.sequence < 0:
        raise ValueError("frame timestamp and sequence are invalid.")
    metadata_bot_id = frame.metadata.get("bot_id")
    if metadata_bot_id is not None and metadata_bot_id != frame.bot_id:
        raise ValueError("frame metadata bot_id does not match frame identity.")
    image = frame.image
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("frame image must be an HxWx3 numpy array.")
    if image.shape[0] <= 0 or image.shape[1] <= 0:
        raise ValueError("frame image dimensions must be positive.")
    return image


def _validate_cards(value: Sequence[DetectedCard]) -> tuple[DetectedCard, ...]:
    if isinstance(value, (str, bytes)):
        raise TypeError("card detector output must be a sequence of DetectedCard.")
    cards = tuple(value)
    if not all(isinstance(card, DetectedCard) for card in cards):
        raise TypeError("card detector returned an invalid item.")
    return tuple(sorted(cards, key=lambda card: (card.zone.value, card.roi.y, card.roi.x, card.code)))


def _validate_buttons(value: Sequence[ButtonState]) -> tuple[ButtonState, ...]:
    if isinstance(value, (str, bytes)):
        raise TypeError("button detector output must be a sequence of ButtonState.")
    buttons = tuple(value)
    if not all(isinstance(button, ButtonState) for button in buttons):
        raise TypeError("button detector returned an invalid item.")
    return tuple(sorted(buttons, key=lambda button: str(button.button_id)))


def _validate_ocr(value: Mapping[str, OcrText]) -> tuple[tuple[str, OcrText], ...]:
    if not isinstance(value, Mapping):
        raise TypeError("OCR detector output must be a mapping.")
    items = tuple(sorted(value.items(), key=lambda item: str(item[0])))
    if not all(isinstance(key, str) and key.strip() and isinstance(item, OcrText) for key, item in items):
        raise TypeError("OCR detector returned an invalid field.")
    return items


def _validate_counts(counts: Mapping[SeatPosition, int]) -> dict[SeatPosition, int]:
    if not isinstance(counts, Mapping):
        raise TypeError("card counts must be a mapping.")
    normalized: dict[SeatPosition, int] = {}
    for seat, count in counts.items():
        if not isinstance(seat, SeatPosition) or isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("card counts must use SeatPosition and integer values.")
        if not 0 <= count <= 13:
            raise ValueError("card counts must be within [0, 13].")
        normalized[seat] = count
    return normalized


class PerceptionPipeline:
    """Run injected perception adapters and produce a safe typed snapshot."""

    def __init__(self, adapters: PerceptionAdapters) -> None:
        self.adapters = adapters

    def process(
        self,
        frame: FrameEnvelope,
        *,
        previous_card_counts: Mapping[SeatPosition, int] | None = None,
        current_card_counts: Mapping[SeatPosition, int] | None = None,
        game_phase: GamePhase = GamePhase.DEALING,
        room_id: str | None = None,
        round_text: str | None = None,
    ) -> PipelineResult:
        failures: list[PipelineFailure] = []
        try:
            image = _validate_frame(frame)
        except (TypeError, ValueError) as exc:
            return PipelineResult(None, (), (PipelineFailure(FailureComponent.FRAME, str(exc)),))

        cards: tuple[DetectedCard, ...] = ()
        try:
            cards = _validate_cards(self.adapters.cards.detect(image.copy()))
        except Exception as exc:  # adapter boundary must fail safe
            failures.append(PipelineFailure(FailureComponent.CARDS, type(exc).__name__))

        buttons: tuple[ButtonState, ...] = ()
        try:
            buttons = _validate_buttons(self.adapters.buttons.detect(image.copy()))
        except Exception as exc:  # adapter boundary must fail safe
            buttons = _safe_buttons()
            failures.append(PipelineFailure(FailureComponent.BUTTONS, type(exc).__name__))

        ocr_fields: tuple[tuple[str, OcrText], ...] = ()
        if self.adapters.ocr is not None:
            try:
                ocr_fields = _validate_ocr(self.adapters.ocr.recognize(image.copy()))
            except Exception as exc:
                failures.append(PipelineFailure(FailureComponent.OCR, type(exc).__name__))

        counts: dict[SeatPosition, int] = {}
        if current_card_counts is not None:
            try:
                counts = _validate_counts(current_card_counts)
            except (TypeError, ValueError) as exc:
                failures.append(PipelineFailure(FailureComponent.TURN, str(exc)))

        turn_owner: SeatPosition | None = None
        turn_evidence: TurnOwnerEvidence | None = None
        if self.adapters.turn is not None and previous_card_counts is not None and current_card_counts is not None:
            try:
                previous = _validate_counts(previous_card_counts)
                current = _validate_counts(current_card_counts)
                detection = self.adapters.turn.detect(
                    image.copy(), previous_card_counts=previous, current_card_counts=current
                )
                if not isinstance(detection, TurnOwnerDetection):
                    raise TypeError("turn detector returned an invalid result.")
                turn_owner = detection.turn_owner
                turn_evidence = detection.evidence
            except Exception as exc:
                turn_owner = None
                turn_evidence = None
                failures.append(PipelineFailure(FailureComponent.TURN, type(exc).__name__))

        confidence_values = [card.confidence for card in cards]
        confidence_values.extend(button.confidence for button in buttons)
        if turn_evidence is not None:
            confidence_values.append(turn_evidence.primary_confidence)
            confidence_values.append(turn_evidence.secondary_confidence)
        confidence = min(confidence_values) if confidence_values else 0.0
        if not math.isfinite(confidence):
            confidence = 0.0

        snapshot = PerceptionSnapshot(
            bot_id=frame.bot_id,
            frame_id=frame.frame_id,
            frame_ts=frame.timestamp_ns,
            confidence=confidence,
            cards=cards,
            player_card_counts=counts,
            turn_owner=turn_owner,
            turn_owner_evidence=turn_evidence,
            buttons=buttons,
            game_phase=game_phase,
            room_id=room_id,
            round_text=round_text,
        )
        return PipelineResult(snapshot, ocr_fields, tuple(failures))
