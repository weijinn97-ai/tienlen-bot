from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from itertools import combinations, product
from typing import Iterable, Sequence

from contracts.interfaces import card_strength, sort_cards, validate_card_code


class InvalidComboError(ValueError):
    pass


class ComboType(str, Enum):
    SINGLE = "single"
    PAIR = "pair"
    TRIPLE = "triple"
    STRAIGHT = "straight"
    FOUR_OF_A_KIND = "four_of_a_kind"
    THREE_CONSECUTIVE_PAIRS = "three_consecutive_pairs"
    FOUR_CONSECUTIVE_PAIRS = "four_consecutive_pairs"


_TYPE_ORDER = {
    ComboType.SINGLE: 0,
    ComboType.PAIR: 1,
    ComboType.TRIPLE: 2,
    ComboType.STRAIGHT: 3,
    ComboType.THREE_CONSECUTIVE_PAIRS: 4,
    ComboType.FOUR_OF_A_KIND: 5,
    ComboType.FOUR_CONSECUTIVE_PAIRS: 6,
}


@dataclass(frozen=True)
class Combo:
    cards: tuple[str, ...]
    combo_type: ComboType
    high_card: str

    @property
    def is_bomb(self) -> bool:
        return self.combo_type in {
            ComboType.THREE_CONSECUTIVE_PAIRS,
            ComboType.FOUR_OF_A_KIND,
            ComboType.FOUR_CONSECUTIVE_PAIRS,
        }


def _rank_strength(card: str) -> int:
    return card_strength(card)[0]


def _normalize_unique_cards(cards: Sequence[str]) -> tuple[str, ...]:
    try:
        normalized = sort_cards(cards)
    except ValueError as exc:
        raise InvalidComboError(str(exc)) from exc
    if len(set(normalized)) != len(normalized):
        raise InvalidComboError("A combo cannot contain duplicate cards.")
    if not normalized:
        raise InvalidComboError("A combo must contain at least one card.")
    return normalized


def _are_consecutive(values: Sequence[int]) -> bool:
    return all(right == left + 1 for left, right in zip(values, values[1:]))


def classify_combo(cards: Sequence[str]) -> Combo:
    normalized = _normalize_unique_cards(cards)
    ranks = [_rank_strength(card) for card in normalized]
    rank_counts = Counter(ranks)
    size = len(normalized)
    high_card = max(normalized, key=card_strength)

    if size == 1:
        combo_type = ComboType.SINGLE
    elif len(rank_counts) == 1 and size == 2:
        combo_type = ComboType.PAIR
    elif len(rank_counts) == 1 and size == 3:
        combo_type = ComboType.TRIPLE
    elif len(rank_counts) == 1 and size == 4:
        combo_type = ComboType.FOUR_OF_A_KIND
    elif (
        size >= 3
        and len(rank_counts) == size
        and 12 not in rank_counts
        and _are_consecutive(sorted(rank_counts))
    ):
        combo_type = ComboType.STRAIGHT
    elif (
        size in {6, 8}
        and all(count == 2 for count in rank_counts.values())
        and 12 not in rank_counts
        and _are_consecutive(sorted(rank_counts))
    ):
        combo_type = (
            ComboType.THREE_CONSECUTIVE_PAIRS
            if size == 6
            else ComboType.FOUR_CONSECUTIVE_PAIRS
        )
    else:
        raise InvalidComboError(f"Cards do not form a supported combo: {normalized!r}")

    return Combo(cards=normalized, combo_type=combo_type, high_card=high_card)


def _as_combo(value: Combo | Sequence[str]) -> Combo:
    return value if isinstance(value, Combo) else classify_combo(value)


def _all_twos(combo: Combo) -> bool:
    return all(_rank_strength(card) == 12 for card in combo.cards)


def beats(challenger: Combo | Sequence[str], target: Combo | Sequence[str]) -> bool:
    challenger_combo = _as_combo(challenger)
    target_combo = _as_combo(target)

    if challenger_combo.combo_type == target_combo.combo_type:
        if (
            challenger_combo.combo_type == ComboType.STRAIGHT
            and len(challenger_combo.cards) != len(target_combo.cards)
        ):
            return False
        return card_strength(challenger_combo.high_card) > card_strength(target_combo.high_card)

    if target_combo.combo_type in {ComboType.SINGLE, ComboType.PAIR} and _all_twos(
        target_combo
    ):
        return challenger_combo.combo_type in {
            ComboType.THREE_CONSECUTIVE_PAIRS,
            ComboType.FOUR_OF_A_KIND,
            ComboType.FOUR_CONSECUTIVE_PAIRS,
        }

    if target_combo.combo_type == ComboType.THREE_CONSECUTIVE_PAIRS:
        return challenger_combo.combo_type in {
            ComboType.FOUR_OF_A_KIND,
            ComboType.FOUR_CONSECUTIVE_PAIRS,
        }

    if target_combo.combo_type == ComboType.FOUR_OF_A_KIND:
        return challenger_combo.combo_type == ComboType.FOUR_CONSECUTIVE_PAIRS

    return False


def _combo_sort_key(combo: Combo) -> tuple[object, ...]:
    return (
        len(combo.cards),
        _TYPE_ORDER[combo.combo_type],
        card_strength(combo.high_card),
        tuple(card_strength(card) for card in combo.cards),
    )


def _response_sort_key(combo: Combo, target: Combo) -> tuple[object, ...]:
    return (
        combo.combo_type != target.combo_type,
        combo.is_bomb,
        len(combo.cards),
        card_strength(combo.high_card),
        tuple(card_strength(card) for card in combo.cards),
    )


def _group_by_rank(cards: Sequence[str]) -> dict[int, tuple[str, ...]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for card in cards:
        grouped[_rank_strength(card)].append(card)
    return {rank: tuple(sorted(values, key=card_strength)) for rank, values in grouped.items()}


def enumerate_combos(hand: Sequence[str]) -> tuple[Combo, ...]:
    normalized = _normalize_unique_cards(hand)
    grouped = _group_by_rank(normalized)
    found: dict[tuple[str, ...], Combo] = {}

    def add(cards: Iterable[str]) -> None:
        combo = classify_combo(tuple(cards))
        found[combo.cards] = combo

    for card in normalized:
        add((card,))

    for rank_cards in grouped.values():
        for size in (2, 3, 4):
            if len(rank_cards) >= size:
                for candidate in combinations(rank_cards, size):
                    add(candidate)

    # Rank 12 is the two and is excluded from straights and consecutive pairs.
    for start in range(12):
        for end in range(start + 2, 12):
            ranks = range(start, end + 1)
            if all(rank in grouped for rank in ranks):
                for candidate in product(*(grouped[rank] for rank in ranks)):
                    add(candidate)

    for run_size in (3, 4):
        for start in range(0, 12 - run_size + 1):
            ranks = range(start, start + run_size)
            if not all(len(grouped.get(rank, ())) >= 2 for rank in ranks):
                continue
            pair_options = [tuple(combinations(grouped[rank], 2)) for rank in ranks]
            for selected_pairs in product(*pair_options):
                add(card for pair in selected_pairs for card in pair)

    return tuple(sorted(found.values(), key=_combo_sort_key))


def enumerate_legal_moves(
    hand: Sequence[str],
    target: Combo | Sequence[str] | None = None,
    *,
    must_include_three_spades: bool = False,
) -> tuple[Combo, ...]:
    combos = enumerate_combos(hand)
    if must_include_three_spades:
        combos = tuple(combo for combo in combos if "3S" in combo.cards)

    if target is None:
        return combos

    target_combo = _as_combo(target)
    legal = (combo for combo in combos if beats(combo, target_combo))
    return tuple(sorted(legal, key=lambda combo: _response_sort_key(combo, target_combo)))


def is_legal_play(
    hand: Sequence[str],
    cards: Sequence[str],
    target: Combo | Sequence[str] | None = None,
    *,
    must_include_three_spades: bool = False,
) -> bool:
    try:
        normalized_hand = _normalize_unique_cards(hand)
        combo = classify_combo(cards)
        if not set(combo.cards).issubset(normalized_hand):
            return False
        if must_include_three_spades and "3S" not in combo.cards:
            return False
        return target is None or beats(combo, target)
    except (InvalidComboError, ValueError):
        return False
