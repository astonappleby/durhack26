#!/usr/bin/env python3
"""Decode three text hand pairs into words using the encoder's ordered word list."""

import argparse
import csv
from pathlib import Path
import re
import sys

from encoder import (
    BACK_PATTERNS,
    FRONT_STATES,
    HAND_CODES,
    HAND_RADIX,
    load_words,
)


def parse_pairs(text: str) -> list[str]:
    """Return six hand descriptions in pair-number order, left then right."""
    hand = r"([LR])\s+([FB])\s+([NESW])\s+([01]{5})"
    pattern = re.compile(rf"Pair\s+([123])\s*:\s*{hand}\s*\|\s*{hand}", re.I)
    pairs = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = pattern.fullmatch(line.strip())
        if match is None:
            raise ValueError(f"Invalid pair: {line!r}. Expected Pair 1: L F N 00000 | R F N 00000")
        number, *fields = match.groups()
        if number in pairs:
            raise ValueError(f"Duplicate Pair {number}.")
        hands = {}
        for offset in (0, 4):
            side, view, direction, bits = fields[offset:offset + 4]
            if side.upper() in hands:
                raise ValueError(f"Pair {number} must contain one left and one right hand.")
            hands[side.upper()] = f"{view.upper()} {direction.upper()} {bits}"
        pairs[number] = [hands['L'], hands['R']]
    if set(pairs) != {'1', '2', '3'}:
        raise ValueError("Exactly Pair 1, Pair 2 and Pair 3 are required.")
    return [hand for number in ('1', '2', '3') for hand in pairs[number]]


def decode(hands: list[str], vocabulary: list[str]) -> tuple[int, str, list[str]]:
    """Invert encoder.encode; hands are six 'F/B N/E/S/W 00000' strings."""
    if len(hands) != 6:
        raise ValueError("Exactly six hand descriptions are required.")
    if not vocabulary or len(vocabulary) ** 3 > HAND_CODES:
        raise ValueError("Word list must be nonempty and fit in the allowed hand codes.")
    codes = []
    for hand in hands:
        match = re.fullmatch(r"\s*([FB])\s+([NESW])\s+([01]{5})\s*", hand, re.I)
        if match is None:
            raise ValueError(f"Invalid hand description: {hand!r}")
        view, direction, fingers = match.groups()
        view = view.upper()
        direction_index = 'NESW'.index(direction.upper())
        if view == 'F':
            pattern_index = sum(
                int(bit) << finger for finger, bit in enumerate(fingers)
            )
            codes.append(direction_index * 32 + pattern_index)
        else:
            try:
                pattern_index = BACK_PATTERNS.index(fingers)
            except ValueError:
                raise ValueError(f"Banned back-of-hand finger pattern: {fingers}") from None
            codes.append(FRONT_STATES + direction_index * len(BACK_PATTERNS) + pattern_index)

    number = 0
    for code in codes:
        number = number * HAND_RADIX + code
    code_text = " ".join(str(code) for code in codes)
    if number >= len(vocabulary) ** 3:
        raise ValueError("Hand code is outside the range of this word list; check the poses and word list.")
    remaining = number
    words = []
    for _ in range(3):
        remaining, index = divmod(remaining, len(vocabulary))
        words.append(vocabulary[index])
    return number, code_text, words[::-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pairs', nargs='?', help='quoted text containing Pair 1, Pair 2 and Pair 3')
    parser.add_argument('-i', '--input', type=Path, help='read pairs from a UTF-8 text file')
    parser.add_argument('--word-list', type=Path,
                        default=Path(__file__).with_name('durhack_word_list.csv'),
                        help='same CSV, in the same order, used for encoding')
    args = parser.parse_args()
    if args.pairs is not None and args.input is not None:
        parser.error('Use quoted pairs or --input, not both.')
    if args.pairs is None and args.input is None and sys.stdin.isatty():
        parser.error('Supply quoted pairs, --input poses.txt, or pipe pair text into stdin.')
    try:
        text = (args.input.read_text(encoding='utf-8-sig') if args.input is not None
                else args.pairs if args.pairs is not None else sys.stdin.read())
        vocabulary = load_words(args.word_list)
        _, _, words = decode(parse_pairs(text), vocabulary)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    print(' '.join(words))


if __name__ == '__main__':
    main()
